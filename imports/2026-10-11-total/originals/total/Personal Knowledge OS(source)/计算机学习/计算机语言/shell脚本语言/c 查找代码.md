查找文件是很有用的技能，但是很多时候您的目标其实是查看文件的内容。一个最常见的场景是您希望查找具有某种模式的全部文件，并找它们的位置。

为了实现这一点，很多类 UNIX 的系统都提供了 [`grep`](https://man7.org/linux/man-pages/man1/grep.1.html) 命令，它是用于对输入文本进行匹配的通用工具。它是一个非常重要的 shell 工具，我们会在后续的数据清理课程中深入的探讨它。

`grep` 有很多选项，这也使它成为一个非常全能的工具。其中我经常使用的有 `-C` ：获取查找结果的上下文（Context）；`-v` 将对结果进行反选（Invert），也就是输出不匹配的结果。举例来说， `grep -C 5` 会输出匹配结果前后五行。当需要搜索大量文件的时候，使用 `-R` 会递归地进入子目录并搜索所有的文本文件。

但是，我们有很多办法可以对 `grep -R` 进行改进，例如使其忽略 `.git` 文件夹，使用多 CPU 等等。

因此也出现了很多它的替代品，包括 [ack](https://beyondgrep.com/), [ag](https://github.com/ggreer/the_silver_searcher) 和 [rg](https://github.com/BurntSushi/ripgrep)。它们都特别好用，但是功能也都差不多，我比较常用的是 ripgrep (`rg`) ，因为它速度快，而且用法非常符合直觉。例子如下：

```
# 查找所有使用了 requests 库的文件
rg -t py 'import requests'
# 查找所有没有写 shebang 的文件（包含隐藏文件）
rg -u --files-without-match "^#!"
# 查找所有的foo字符串，并打印其之后的5行
rg foo -A 5
# 打印匹配的统计信息（匹配的行和文件的数量）
rg --stats PATTERN
```

与 `find`/`fd` 一样，重要的是你要知道有些问题使用合适的工具就会迎刃而解，而具体选择哪个工具则不是那么重要。