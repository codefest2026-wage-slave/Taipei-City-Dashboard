WORKDIR /root
RUN --mount=type=cache,sharing=locked,mode=0777,target=/root/.cache/uv,id=uv \ 
	--mount=from=ghcr.io/astral-sh/uv:0.11.7,source=/uv,target=/usr/bin/uv \
	--mount=type=bind,target=requirements.txt,src=requirements.txt \
	uv venv -p 3.12 && \
	uv pip install -r requirements.txt
ENV PATH="/root/.venv/bin:$PATH" \
    UV_PYTHON=/root/.venv/bin/python
