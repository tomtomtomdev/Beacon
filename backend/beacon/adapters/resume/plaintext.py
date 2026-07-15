"""PlainTextResumeParser — paste text or a .txt upload, zero dependencies.

The always-available resume-parse path (SPEC §11): the feature never *requires* a parser
dependency. PdfResumeParser is a deliberate later drop-in behind the same ResumeParser port
(would add one scoped dep, e.g. pypdf); until then a PDF upload is rejected here so the caller
can steer the user to paste or a .txt file.
"""

_TEXT_KINDS = frozenset({"text", "txt", "text/plain"})


class PlainTextResumeParser:
    def parse(self, data: bytes | str, kind: str) -> str:
        if kind not in _TEXT_KINDS:
            raise ValueError(
                f"PlainTextResumeParser cannot parse {kind!r}; paste text or upload a .txt file"
            )
        return data.decode("utf-8") if isinstance(data, bytes) else data
