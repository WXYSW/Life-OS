==核心功能==：env 是一个 命令行工具（通常位于 /usr/bin/env），其主要作用是：
	打印环境变量：
		不带参数运行时，它会打印出当前用户的环境变量及其值（就是你在终端输入 env 后看到的内容）。
	在修改后的环境中运行命令：
		你可以用它来临时设置、修改或删除环境变量，然后在那个修改后的环境下运行指定的命令。例如：env PATH=/new/path:$PATH DEBUG=1 my_script.sh 会在设置好 PATH 和 DEBUG 环境变量后运行 my_script.sh。
	在 PATH 中查找并运行命令：
		这是它在 shebang 行中最关键的作用！当你像这样使用它 env command_name 时：
			1     env 会查看当前的环境变量 PATH。
			2     它会沿着 PATH 中列出的目录顺序进行搜索。
		    3    找到第一个名字叫 command_name 的可执行文件。
			4     然后执行这个找到的可执行文件。