touch 主要用于 修改文件时间戳 或 创建空文件。

touch [选项]... 文件名...
1. **创建空文件**（文件不存在时）
    touch newfile.txt  # 创建 newfile.txt（若不存在）
2. **更新文件时间戳**（文件存在时）  
    默认将文件的 **访问时间（atime）** 和 **修改时间（mtime）** 设为当前时间：
    bash
    touch existing.txt  # 更新 existing.txt 的时间戳

-a                                 仅更新 访问时间（atime）
-m	                            仅更新 修改时间（mtime）
-c / --no-create	        不创建新文件（仅更新现有文件）
-d / --date="STRING"	指定时间（如 -d "2024-01-01 12:00"）
-r / --reference=FILE	复制其他文件的时间戳（如 -r ref.txt file.txt）
-t	                                使用 [[CC]YY]MMDDhhmm[.ss] 格式指定时间（如 -t 202407171200.30）
