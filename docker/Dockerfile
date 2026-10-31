FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/home/frappe/.local/bin:$PATH

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

RUN mkdir -p /home/frappe/.config/pip \
 && printf '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\ntrusted-host = pypi.tuna.tsinghua.edu.cn\ntimeout = 120\nretries = 10\n' > /home/frappe/.config/pip/pip.conf \
 && pip3 install --user --no-cache-dir frappe-bench==5.31.1

# 从 Gitee 镜像克隆 Frappe v15（国内网络，比 github.com 快一个数量级）
# 只保留 version-15 的浅克隆，体积约 40 MB
RUN git clone --depth 1 --branch version-15 \
      https://gitee.com/mirrors/frappe.git /home/frappe/frappe-src \
 && cd /home/frappe/frappe-src \
 && git remote set-url origin https://github.com/frappe/frappe.git

# 用本地源码初始化 bench，不再走网络
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
