# bench 基础镜像：内部已完成 bench init（Frappe v15），供 init / frappe 两个服务复用
# 由 docker-compose.yml 里的 bench-base 服务自动构建，无需手动 docker build
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/home/frappe/.local/bin:$PATH

# 系统依赖：MariaDB 客户端、Redis、wkhtmltopdf（打印）、构建工具
RUN apt-get update \
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

# bench CLI + Frappe v15（--skip-assets：assets 在 install-app 后按需构建，避免构建阶段长时间编译）
RUN pip3 install --user --no-cache-dir frappe-bench==5.24.0 \
 && bench init --frappe-branch version-15 --skip-assets --skip-redis-config-generation frappe-bench \
 && cd frappe-bench \
 && bench set-config -g db_host mariadb \
 && bench set-config -g redis_cache redis://redis:6379/1 \
 && bench set-config -g redis_queue redis://redis:6379/2 \
 && bench set-config -g redis_socketio redis://redis:6379/3

WORKDIR /home/frappe/frappe-bench

EXPOSE 8000
CMD ["bench", "start"]
