"""领域模块包（按子域分组，04-backend-design §2.1/§3）。

跨域调用只能 import 对方 service.py 公开函数；禁止 import 对方 models / repository（ADR-0011）。
"""
