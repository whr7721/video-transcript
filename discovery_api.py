from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import discovery

router = APIRouter(prefix='/api/discovery')


def call(fn, *args):
    try:
        return fn(*args)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None


class Selection(BaseModel):
    revision: int = Field(ge=1)
    video_ids: list[str] = Field(max_length=100)


class Resume(BaseModel):
    max_candidates_total: int = Field(ge=1, le=100, strict=True)


@router.get('')
def jobs():
    return [{'id': v['id'], 'topic': v['request']['topic'], 'state': v['state'],
             'count': len(v['items']), 'created_at': v['created_at']} for v in discovery.all_jobs()]


@router.post('')
def create(body: discovery.Search):
    return call(discovery.start, body)


@router.get('/{ident}')
def detail(ident: str):
    return discovery.public(call(discovery.get, ident))


@router.post('/{ident}/resume')
def resume(ident: str, body: Resume):
    return call(discovery.resume, ident, body.max_candidates_total)


@router.put('/{ident}/selection')
def selection(ident: str, body: Selection):
    return call(discovery.select, ident, body.revision, body.video_ids)
