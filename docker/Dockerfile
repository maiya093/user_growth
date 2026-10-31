FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/home/frappe/.local/bin:$PATH
ENV UV_HTTP_TIMEOUT=300
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.tuna.tsinghua.edu.cn@g; s@//security.ubuntu.com@//mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      curl wget ca-certificates git sudo \
      python3.10 python3.10-dev python3-pip python3.10-venv \
      mariadb-client libmariadb-dev \
      redis-tools \
      build-essential pkg-config \
      libffi-dev libssl-dev \
      nodejs npm \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash frappe \
 && echo "frappe ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/frappe \
 && chmod 0440 /etc/sudoers.d/frappe

USER frappe
WORKDIR /home/frappe

# 所有 github.com 的 git 请求（包括依赖里写死的 git+https）统一走 ghproxy 代理
RUN git config --global url."https://gh-proxy.com/https://github.com/".insteadOf "https://github.com/" \
 && git config --global http.postBuffer 524288000 \
 && git config --global http.lowSpeedLimit 1000 \
 && git config --global http.lowSpeedTime 600

# pip 走清华源（bench CLI 本身用 pip 装）
RUN mkdir -p /home/frappe/.config/pip \
 && printf '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\ntrusted-host = pypi.tuna.tsinghua.edu.cn\ntimeout = 180\nretries = 10\n' > /home/frappe/.config/pip/pip.conf \
 && pip3 install --user --no-cache-dir frappe-bench==5.31.1

# Frappe 源码从 Gitee 镜像克隆（实测有 version-15 分支且速度快）
RUN git clone --depth 1 --branch version-15 \
      https://gitee.com/mirrors/frappe.git /home/frappe/frappe-src

# 用本地源码初始化 bench；依赖中的 GitHub git 包由上面的 insteadOf 自动走代理
RUN bench init --frappe-branch version-15 \
      --frappe-path /home/frappe/frappe-src \
      --skip-assets --skip-redis-config-generation frappe-bench \
 && cd frappe-bench \
 && bench set-config -g db_host mariadb \
 && bench set-config -g redis_cache redis://redis:6379/1 \
 && bench set-config -g redis_queue redis://redis:6379/2 \
 && bench set-config -g redis_socketio redis://redis:6379/3

WORKDIR /home/frappe/frappe-bench

EXPOSE 8000
CMD ["bench", "start"]
