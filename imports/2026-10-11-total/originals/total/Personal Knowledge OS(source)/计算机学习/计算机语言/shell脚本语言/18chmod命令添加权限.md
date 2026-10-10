步骤 1：确认当前权限状态

ls -l semester

如果显示类似 `-rw-r--r--`（缺少 `x`），说明文件没有执行权限

步骤 2：添加执行权限

给文件所有者添加执行权限
chmod u+x ==semester==

验证权限变化

ls -l ==semester==

现在应显示 -rwxr--r-- 或类似（包含 x）