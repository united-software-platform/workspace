# Контейнер формальной проверки требований (change add-formal-validation, design D6).
# SPOT ставится из официального apt-репозитория LRDE (страница установки Spot,
# https://spot.lre.epita.fr/install.html) — канал GPG-подписан, python3-spot бинарный;
# репозиторий собран под текущий Debian stable, поэтому база — trixie (python 3.13).
# z3 — свежий пин из PyPI. Сборка — задачей mise formal-image; после сборки прогоны
# офлайн: контейнер никуда не ходит.
FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl python3 python3-pip python3-yaml \
    && rm -rf /var/lib/apt/lists/* \
    && install -d /etc/apt/keyrings \
    && curl -fsSL https://www.lre.epita.fr/repo/debian.gpg \
        -o /etc/apt/keyrings/lre-epita.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/lre-epita.gpg] http://www.lre.epita.fr/repo/debian/ stable/" \
        > /etc/apt/sources.list.d/lre-epita.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3-spot \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages z3-solver==5.4.1.0

WORKDIR /work
