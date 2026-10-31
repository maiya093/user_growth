FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/home/frappe/.local/bin:$PATH
ENV UV_HTTP_TIMEOUT=300
ENV UV_GIT_TIMEOUT=300

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

# git 全局重写：所有 github.com 请求走国内代理（依赖里写死的 git+https 地址也会被重写）
RUN git config --global url."https://gitclone.com/github.com/".insteadOf "https://github.com/" \
 && git config --global http.postBuffer 524288000 \
 && git config --global http.lowSpeedLimit 1000 \
 && git config --global http.lowSpeedTime 600 \
 && git config --global http.sslVerify false

RUN mkdir -p /home/frappe/.config/pip \
 && printf '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\ntrusted-host = pypi.tuna.tsinghua.edu.cn\ntimeout = 180\nretries = 10\n' > /home/frappe/.config/pip/pip.conf \
 && pip3 install --user --no-cache-dir frappe-bench==5.31.1

# 用代理克隆 Frappe v15 源码
RUN git clone --depth 1 --branch version-15 \
      https://github.com/frappe/frappe.git /home/frappe/frappe-src

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
