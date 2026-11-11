from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile, status

from app.api.deps import CurrentUserDep, DbDep, PageParams, require
from app.models.ai import AiConversation, AiMessage
from app.models.knowledge import Document
from app.schemas.common import Page
from app.schemas.knowledge import (
    ChatIn,
    ChatOut,
    ConversationOut,
    DocumentOut,
    MessageOut,
    SearchIn,
    SearchOut,
)
from app.services.audit import audit_log
from app.services.knowledge.extract import UnsupportedDocument, detect_kind
from app.services.knowledge.rag import rag_answer
from app.services.knowledge.retriever import hybrid_search
from app.services.storage import get_storage
from app.workers.tasks import ingest_document

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

MAX_DOC_BYTES = 50 * 1024 * 1024


@router.post("/upload", response_model=DocumentOut, status_code=202)
async def upload_document(
    request: Request, file: UploadFile, current: CurrentUserDep, db: DbDep,
    background: BackgroundTasks,
):
    """Async ingestion: returns 202 and processes in background (extraction,
    chunking, embedding, indexing)."""
    require("manage_documents")(current)
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 50 MB limit")
    try:
        kind = detect_kind(file.filename or "", file.content_type)
    except UnsupportedDocument as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc))

    doc = Document(
        org_id=current.org_id,
        title=(file.filename or "document").rsplit(".", 1)[0][:200],
        filename=file.filename or "document",
        mime=file.content_type or f"application/{kind}",
        size_bytes=len(data),
        status="pending",
        created_by=current.id,
    )
    db.add(doc)
    db.flush()
    doc.file_key = get_storage().save(data, doc.filename, "documents")
    audit_log(db, org_id=current.org_id, user_id=current.id, action="document_upload",
              resource="document", resource_id=doc.id,
              ip=request.client.host if request.client else None)
    db.commit()
    db.refresh(doc)
    background.add_task(ingest_document, doc.id)
    return DocumentOut.model_validate(doc)


@router.get("/documents", response_model=Page[DocumentOut])
def list_documents(current: CurrentUserDep, db: DbDep, page: PageParams, status_filter: str | None = None):
    q = db.query(Document).filter(Document.org_id == current.org_id)
    if status_filter:
        q = q.filter(Document.status == status_filter)
    total = q.count()
    items = q.order_by(Document.created_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[DocumentOut](
        items=[DocumentOut.model_validate(d) for d in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, current: CurrentUserDep, db: DbDep):
    require("manage_documents")(current)
    doc = db.query(Document).filter(Document.id == document_id, Document.org_id == current.org_id).first()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    db.delete(doc)  # chunks cascade
    db.commit()
    return None


@router.post("/search", response_model=SearchOut)
def search(payload: SearchIn, current: CurrentUserDep, db: DbDep):
    results, method = hybrid_search(
        db, current.org_id, payload.query,
        top_k=payload.top_k, document_ids=payload.document_ids,
    )
    return SearchOut(query=payload.query, results=results, retrieval_method=method)


@router.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, current: CurrentUserDep, db: DbDep):
    """Grounded RAG chat with citations and safeguard behavior."""
    if payload.conversation_id:
        conv = db.query(AiConversation).filter(
            AiConversation.id == payload.conversation_id,
            AiConversation.org_id == current.org_id,
            AiConversation.kind == "rag",
        ).first()
    else:
        conv = None
    if conv is None:
        conv = AiConversation(org_id=current.org_id, user_id=current.id, kind="rag",
                              title=payload.message[:60])
        db.add(conv)
        db.flush()

    db.add(AiMessage(conversation_id=conv.id, role="user", content=payload.message))
    result = rag_answer(db, current.org_id, payload.message, top_k=payload.top_k)
    db.add(AiMessage(
        conversation_id=conv.id, role="assistant", content=result["answer"],
        citations=result["citations"],
        meta={"llm_provider": result["llm_provider"], "retrieval_method": result["retrieval_method"],
              "has_context": result["has_context"], "injection_flags": result["injection_flags"]},
    ))
    db.commit()
    return ChatOut(
        conversation_id=conv.id, answer=result["answer"], citations=result["citations"],
        llm_provider=result["llm_provider"], has_context=result["has_context"],
        disclaimer=result["disclaimer"],
    )


@router.get("/conversations", response_model=Page[ConversationOut])
def list_conversations(current: CurrentUserDep, db: DbDep, page: PageParams, kind: str = "rag"):
    q = db.query(AiConversation).filter(AiConversation.org_id == current.org_id, AiConversation.kind == kind)
    total = q.count()
    items = q.order_by(AiConversation.updated_at.desc()).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[ConversationOut](
        items=[ConversationOut.model_validate(c) for c in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )


@router.get("/conversations/{conversation_id}/messages", response_model=Page[MessageOut])
def list_messages(conversation_id: int, current: CurrentUserDep, db: DbDep, page: PageParams):
    conv = db.query(AiConversation).filter(
        AiConversation.id == conversation_id, AiConversation.org_id == current.org_id
    ).first()
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    q = db.query(AiMessage).filter(AiMessage.conversation_id == conversation_id)
    total = q.count()
    items = q.order_by(AiMessage.id).offset((page["page"] - 1) * page["page_size"]).limit(page["page_size"]).all()
    return Page[MessageOut](
        items=[MessageOut.model_validate(m) for m in items], total=total,
        pages=max(1, -(-total // page["page_size"])), page=page["page"], page_size=page["page_size"],
    )
