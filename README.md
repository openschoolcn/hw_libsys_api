🏫 汇文软件 Libsys 图书管理系统 API

求 ⭐⭐⭐⭐⭐（跪

---

## 功能实现

- [x] 登录（自动识别是否需要验证码或是否需要身份认证）
- [x] 个人信息
- [x] 当前借阅
- [x] 借阅历史
- [x] 账单列表
- [x] 账单详情
- [x] 热门书籍
- [x] 搜书书籍
- [x] 书籍详情

## 状态码

为了一些特殊的业务逻辑，如验证码错误后自动刷新页面获取等，使用了自定义状态码，详情如下：

| 状态码 | 内容                 |
| ------ | -------------------- |
| 998    | 网页弹窗未处理内容   |
| 999    | 接口逻辑或未知错误   |
| 1000   | 请求获取成功         |
| 1001   | （登录）需要验证码   |
| 1002   | 用户名或密码不正确   |
| 1003   | 请求超时             |
| 1004   | 验证码错误           |
| 1005   | 内容为空             |
| 1006   | cookies 失效或过期   |
| 1011   | 需要身份验证         |
| 2333   | 系统维护或服务被 ban |

## Tips⚠️

- 请先在 `config.json` 中修改图书管理系统 `base_url` 。
  - 只需填写`https://xxx.com`到 base_url 中，拼接后与类中 `self.xxurl` 不同的路径部分在 API 代码内增删改。
- 一个简单的测试示例

  ```python
    # example.py
    import base64
    import os
    import sys
    from pprint import pprint

    from hw_libsys_api import Client

    cookies = {}

    user = Client(cookies=cookies)

    # 不需要登录
    # result = user.get_recommendation_books()
    # result = user.search_book("title", "Python", 1)
    # result = user.get_book_detail("4b6a45352b52432f4b577a66676838626476376f38773d3d")

    if cookies == {}:
        lgn = user.login("uid", "password")
        if lgn["code"] == 1001:
            verify_data = lgn["data"]
            with open(os.path.abspath("captcha.png"), "wb") as pic:
                pic.write(base64.b64decode(verify_data.pop("captcha_pic")))
            verify_data["captcha"] = input("输入验证码：")
            ret = user.login_with_captcha(**verify_data)
            if ret["code"] == 1011:
                pprint(ret)
                name = input("输入真实姓名：")
                new_password = input("输入新密码：")
                ret = user.ini_verify(name, new_password)
                pprint(ret)
                sys.exit()
            elif ret["code"] != 1000:
                pprint(ret)
                sys.exit()
            pprint(ret)
        elif lgn["code"] != 1000:
            pprint(lgn)
            sys.exit()

    result = user.get_info()
    # result = user.get_borrow_list()
    # result = user.get_borrow_history()
    # result = user.get_pay_list()
    # result = user.get_pay_detail()

    pprint(result, sort_dicts=False)


  ```

## 部分数据字段说明

```json
{
  // 个人信息
  "cert_start": "证件办理日期",
  "cert_work": "证件生效日期",
  "cert_end": "证件过期日期",
  "max_borrow": "最多可借数量",
  "max_order": "最多可预约数量",
  "max_entrust": "最多可委托数量",
  "overdue": "超期图书数量",
  "type": "读者类型",
  "level": "借阅等级",
  "cumulative_borrow": "累计借书",
  "violation_num": "违章次数",
  "violation_money": "欠款金额",
  "deposit": "押金",
  "charge": "手续费",
  "percent": "超过百分之多少的读者",
  // 书籍
  "type": "书籍类型",
  "title": "标题",
  "full_title": "标题（全称）",
  "oth_title": "其它标题",
  "author": "作者",
  "oth_author": "其它作者",
  "category": "学科主题",
  "publisher": "出版社",
  "isbn": "ISBN/ISSN",
  "physical": "载体形态项",
  "notes": "一般附注",
  "author_notes": "责任者附注",
  "abstract": "摘要",
  "annual_roll": "年卷期",
  "location": "馆藏地",
  "return_location": "还书位置",
  "status": "书刊状态",
  "borrow_date": "借阅日期",
  "return_date": "归还日期",
  "due_date": "到期日",
  "total_num": "馆藏数量",
  "loanable_num": "可借数量",
  "borrowed_num": "被借阅数量",
  "borrowed_times": "被借阅次数",
  "borrowed_ratio": "借阅比",
  "bar_code": "条码号",
  "marc_no": "跳转ID",
  "call_no": "索书号",
  // 账单
  "description": "账单描述",
  "date": "结算日期",
  "type": "结算项目",
  "refund": "退款",
  "contribution": "缴款",
  "pay_method": "结算方式",
  "bill_no": "票据号",
  "payable": "应缴",
  "payin": "实缴",
  "state": "状态"
}
```
