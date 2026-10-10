注意事项：  ==foo = bar== （使用空格隔开）是不能正确工作的，因为解释器会调用程序 foo 并将 = 和 bar 作为参数。 总的来说，在 shell 脚本中使用空格会起到分割参数的作用，有时候可能会造成混淆

变量赋值的语法是 foo=bar，访问变量中存储的数值，其语法为 $foo

foo=bar
echo "$foo"
打印 bar
echo '$foo'
 打印 $foo
