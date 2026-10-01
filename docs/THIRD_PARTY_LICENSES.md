# 第三方许可与数据说明

## pywubi（86 版五笔码表来源）

本项目 `data/wubi86.json`、`data/jianma.json` 由
[pywubi](https://pypi.org/project/pywubi/) 0.3.0 附带的 `wubi_86.json`
（21004 字，含全码与各级简码）按“简码优先”规则整理而来。

```text
MIT License

Copyright (c) 2019  Thunder Bouble

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

如需重建码表，可执行 `tools/make_data.py`，详见 README。

## 练习文章

练习材料在运行时从人民日报电子版（`paper.people.com.cn`）抓取，仅缓存在
本机 `data/cache/` 目录（已在 `.gitignore` 中排除），不在本仓库中分发。
文章版权归人民日报所有，本项目仅用于个人打字练习。

## 五笔字根与编码

五笔字型（86 版）字根、键位与编码属于公开的输入法规范，本项目仅做整理与教学展示。
