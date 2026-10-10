基本用法
bash
sudo [选项] <命令>
最常见的用法： 执行需要 root 权限的命令。

bash
sudo apt update         # 更新软件包列表 (Debian/Ubuntu)
sudo systemctl restart apache2  # 重启 Apache 服务
sudo nano /etc/hosts    # 编辑系统 hosts 文件
sudo shutdown -h now    # 立即关机
以其他用户身份执行命令 (使用 -u 选项)：

bash
sudo -u username whoami  # 以用户 `username` 的身份执行 `whoami` 命令



提升权限：

普通用户在日常操作中没有权限修改系统文件、安装软件、管理服务等。

当需要执行这些特权操作时，在命令前加上 sudo（例如 sudo apt update），输入自己的用户密码（不是 root 密码）进行验证。

验证通过后，该命令就会以 root 权限执行。

安全机制：

避免滥用 root： 系统管理员不需要把 root 密码告诉普通用户，大大降低了安全风险。用户只在需要时临时获取权限。

精细控制： 系统管理员可以通过配置文件 (/etc/sudoers) 精确控制：

哪些用户或用户组可以使用 sudo。

这些用户能以谁的身份（通常是 root，也可以是其他用户）执行命令。

这些用户能执行哪些特定的命令（甚至可以限制命令的参数）。

审计追踪： 所有通过 sudo 执行的命令都会被记录在系统日志中（通常是 /var/log/auth.log 或 /var/log/secure），记录内容包括哪个用户、在什么时间、执行了什么命令。这提供了重要的审计线索。

替代 su：

过去常用 su 命令切换到 root 用户（需要知道 root 密码），然后执行一系列操作，最后退出。这种方式有几个缺点：

需要共享 root 密码。

用户在 root shell 下操作时权限过大，容易误操作。

难以追踪具体是谁在 root 下执行了哪些命令（因为都记录为 root）。

sudo 通常被认为是更安全、更可控的替代方案