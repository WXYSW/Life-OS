'^last-modified:'：搜索以 "last-modified:" 开头的行

`-i`：忽略大小写

`~`  ：代表主目录
	cat ~/last-modified.txt：查看主目录下的
	last-modified.txt文件
	cat last-modified.txt：查看当前目录下的
	last-modified.txt文件。

cut：文本切割工具

-d ' '：用空格作为分隔符

-f2-：取第2列到最后一列

在 bash 中进行比较时，尽量使用双方括号 `[[ ]]` 而不是单方括号 `[ ]`

注意，脚本并不一定只有用 bash 写才能在终端里调用。比如说，这是一段 Python 脚本，作用是将输入的参数倒序输出：

```
#!/usr/local/bin/python
import sys
for arg in reversed(sys.argv[1:]):
    print(arg)
```

内核知道去用 python 解释器而不是 shell 命令来运行这段脚本，是因为脚本的开头第一行的 [shebang](https://en.wikipedia.org/wiki/Shebang_\(Unix\))。


- **终端中显示时启用颜色**：当输出直接显示在终端（TTY）时，自动添加颜色标记
    
- **重定向时禁用颜色**：当输出被重定向到文件/管道（如 `ls > file.txt` 或 `ls | grep...`）时，自动**关闭**颜色标记，避免写入难读的ANSI转义码