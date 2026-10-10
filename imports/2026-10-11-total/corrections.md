# 知识纠错与待核查

原笔记保留，本文件为助手补充。历史笔记中的错误不等于用户现在一定不会。

- SRC-063/066：go过去式went，过去分词gone。[British Council](https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/irregular-verbs)。
- SRC-064：fry→frying，fried为过去式/过去分词；see→seeing，saw为过去式，seen为过去分词。[Cambridge](https://dictionary.cambridge.org/us/dictionary/english/fry)，[British Council](https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/irregular-verbs)。
- SRC-093/103/112：数组不是const指针；sizeof实际数组与函数参数指针不同。常量限定变量不自动成为C语言整型常量表达式。见[C11公开草案](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf) 6.3.2.1、6.7.6.2、6.7.6.3、6.5.3.4；标准版本需区分。
- SRC-106：闭区间二分循环漏掉最后候选，key/k命名不一致；代码片段没有执行，先以边界诊断题检验。
- SRC-122/138：stderr文本与退出状态不同，$?读取状态，$$为进程ID。[GNU退出状态](https://www.gnu.org/s/bash/manual/html_node/Exit-Status.html)，[特殊参数](https://www.gnu.org/software/bash/manual/html_node/Special-Parameters.html)。
- SRC-133：末尾绝对/相对标签倒置，/开头是Unix绝对路径。其他Shell语法片段保留为待核验，不执行文件中的rm、sudo或安装命令。
- 还需逐项核查：SRC-057 competition译成竞争者；SRC-059 as soon as possible、having to；SRC-060 experiment、fruid、pork等词义/拼写；SRC-061/062介词过度简化；SRC-083素数判断解释、SRC-085计数数组初始化、SRC-086辗转相除变量、SRC-118循环边界。尚未逐项给出验证后的标准答案，不进入训练评分依据。

未核验的155个候选状态needs_validation；6个诊断入口status=pending。不创建历史作答、不标记当前掌握。
