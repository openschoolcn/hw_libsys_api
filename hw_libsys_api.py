import base64
import time
import json
import os
import re
import traceback
from urllib.parse import urljoin

import requests
from pyquery import PyQuery as pq
from requests import exceptions
import random


def get_config(section: str, field: str):
    filename = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(filename):
        raise Exception("配置文件不存在")
    with open(filename, "r", encoding="UTF-8") as f:
        config = json.loads(f.read())
    return config.get(section, {}).get(field)


BASE_URL = get_config("library", "base_url")
TIMEOUT = get_config("request", "timeout")


class Client:
    def __init__(self, cookies={}):
        self.login_url = urljoin(BASE_URL, "/reader/login.php")
        self.ep_url = urljoin(BASE_URL, "/reader/ajax_ep.php")
        self.captcha_url = urljoin(BASE_URL, "/reader/captcha.php")
        self.verify_url = urljoin(BASE_URL, "/reader/redr_verify.php")
        self.redr_url = urljoin(BASE_URL, "/reader/redr_con.php")
        self.redr_result_url = urljoin(BASE_URL, "/reader/redr_con_result.php")
        self.headers = requests.utils.default_headers()
        self.headers["Referer"] = self.login_url
        self.headers[
            "User-Agent"
        ] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36"
        self.headers[
            "Accept"
        ] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3"
        self.sess = requests.Session()
        self.sess.keep_alive = False
        self.cookies = cookies

    def login(self, uid, password):
        """登录页"""
        try:
            req_csrf = self.sess.get(
                self.login_url, headers=self.headers, timeout=TIMEOUT
            )
            doc_csrf = pq(req_csrf.text)
            csrf_token = doc_csrf("input[name='csrf_token']").attr("value")
            req_sca = self.sess.get(self.ep_url, headers=self.headers, timeout=TIMEOUT)
            sca = re.findall(r"setAttribute\(\"value\"\,\"(.*)\"\);", req_sca.text)[0]
            req_captcha = self.sess.get(
                self.captcha_url, headers=self.headers, timeout=TIMEOUT
            )
            captcha_pic = base64.b64encode(req_captcha.content).decode()
            return {
                "code": 1001,
                "msg": "获取验证码成功",
                "data": {
                    "csrf_token": csrf_token,
                    "cookies": self.sess.cookies.get_dict(),
                    "number": uid,
                    "sca": sca,
                    "password": password,
                    "captcha_pic": captcha_pic,
                },
            }
        except exceptions.Timeout:
            return {"code": 1003, "msg": "登录超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"登录时未记录的错误：{str(e)}"}

    def login_with_captcha(
        self, csrf_token, cookies, number, sca, password, captcha, **kwargs
    ):
        """验证码登录"""
        try:
            data = {
                "sca": sca,
                "number": number,
                "passwd": self.encode_password(sca, password),
                "captcha": captcha,
                "select": "cert_no",
                "returnUrl": "",
                "csrf_token": csrf_token,
            }
            req_login = self.sess.post(
                self.verify_url,
                headers=self.headers,
                cookies=cookies,
                data=data,
                timeout=TIMEOUT,
                allow_redirects=False,
            )
            doc = pq(req_login.text)
            error = doc("font#fontMsg[color='red']")
            if error.text() != "":
                error_msg = error.text()
                if "用户名或密码错误" in error_msg:
                    return {"code": 1002, "msg": "用户名或密码不正确"}
                elif "验证码" in error_msg:
                    return {"code": 1004, "msg": "验证码输入错误"}
                return {"code": 999, "msg": "错误：" + error_msg}
            self.cookies = self.sess.cookies.get_dict()
            # 未身份认证
            if req_login.headers["Location"] == "redr_con.php":
                return {"code": 1011, "msg": "需要身份认证"}
            else:
                return {
                    "code": 1000,
                    "msg": "登录成功",
                    "data": {"cookies": self.cookies},
                }
        except exceptions.Timeout:
            return {"code": 1003, "msg": "验证码登录超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"验证码登录时未记录的错误：{str(e)}"}

    def ini_verify(self, name, new_password):
        """初次登录系统的身份认证"""
        try:
            if not self.check_password(new_password):
                return {"code": 999, "msg": "新密码不符合要求"}
            req_redr = self.sess.get(
                self.redr_url,
                headers=self.headers,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc_csrf = pq(req_redr.text)
            csrf_token = doc_csrf("input#csrf_token").attr("value")
            if "未完成身份认证" in req_redr.text:
                data = {
                    "csrf_token": csrf_token,
                    "name": name,
                    "new_passwd": new_password,
                    "chk_passwd": new_password,
                }
                req_result = self.sess.post(
                    self.redr_result_url,
                    headers=self.headers,
                    cookies=self.cookies,
                    data=data,
                    timeout=TIMEOUT,
                )
                doc = pq(req_result.text)
                tips = doc(".iconerr")
                if str(tips) != "" and "密码修改成功" in tips.text():
                    return {"code": 1000, "msg": "密码修改成功，请重新登录"}
                error = doc("font[color='red']")
                if error.text() != "":
                    error_msg = error.text()
                    if "身份验证失败" in error_msg:
                        return {"code": 999, "msg": "姓名不匹配，身份验证失败"}
                    return {"code": 998, "msg": "错误：" + error_msg}
                return {"code": 999, "msg": "身份认证时未记录的错误"}
            else:
                return {"code": 999, "msg": "身份认证时未记录的错误"}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "身份认证超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"身份认证时未记录的错误：{str(e)}"}

    def get_info(self):
        """获取图书馆个人信息"""
        url_index = urljoin(BASE_URL, "/reader/redr_info.php")
        url_info = urljoin(BASE_URL, "/reader/redr_info_rule.php")
        try:
            req_index = self.sess.get(
                url_index,
                headers=self.headers,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc_index = pq(req_index.text)
            if doc_index("h5.box_bgcolor").text() == "登录我的图书馆":
                return {"code": 1006, "msg": "登录过期，请重新登录"}
            access_list = [
                n.text().replace(" ", "") for n in doc_index(".bigger-170").items()
            ]
            max_borrow = access_list[0]
            max_order = access_list[1]
            max_entrust = access_list[2]
            overdue = doc_index("span.infobox-data-number:first").text()
            percent = doc_index(".Num").text()
            req_info = self.sess.get(
                url_info,
                headers=self.headers,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc_info = pq(req_info.text)
            trs = list(doc_info("div#mylib_info tr").items())
            info_list = []
            # TODO: 优化
            for i in range(9):
                tr = trs[i].text()
                detail_list = re.findall(r"：(.*)", str(tr))
                for j in detail_list:
                    info_list.append(j)
            result = {
                "name": info_list[0],
                "cert_start": info_list[4],
                "cert_work": info_list[5],
                "cert_end": info_list[3],
                "max_borrow": max_borrow,
                "max_order": max_order,
                "max_entrust": max_entrust,
                "overdue": overdue,
                "type": info_list[9],
                "level": info_list[10],
                "cumulative_borrow": info_list[11],
                "violation_num": info_list[12],
                "violation_money": info_list[13],
                "sex": info_list[20],
                "deposit": info_list[27],
                "charge": info_list[28],
                "percent": percent,
            }
            return {"code": 1000, "msg": "获取个人信息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取个人信息超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"获取个人信息时未记录的错误：{str(e)}"}

    def get_borrow_list(self):
        """获取当前借阅列表"""
        url = urljoin(BASE_URL, "/reader/book_lst.php")
        try:
            req_borrow = self.sess.get(
                url,
                headers=self.headers,
                cookies=self.cookies,
                timeout=TIMEOUT,
            )
            doc = pq(req_borrow.text)
            if doc("h5.box_bgcolor").text() == "登录我的图书馆":
                return {"code": 1006, "msg": "登录过期，请重新登录"}
            if str(doc(".iconerr")) != "":
                return {"code": 1005, "msg": "当前无借阅"}

            trs = list(doc("table:eq(0) tr").items())
            result = {
                "now": doc("div#mylib_content p[style='margin:10px auto;'] b:first")
                .text()
                .strip(),
                "max": doc("div#mylib_content p[style='margin:10px auto;'] b:eq(1)")
                .text()
                .strip(),
                "books": [
                    {
                        "title": trs[i]("td:eq(1) a.blue").text(),
                        "author": trs[i]("td:eq(1)").text().split("/")[1].strip(),
                        "location": trs[i]("td:eq(5)").text(),
                        "borrow_date": trs[i]("td:eq(2)").text(),
                        "due_date": trs[i]("td:eq(3)").text().strip(),
                        "cnum": trs[i]("td:eq(4)").text(),
                        "bar_code": trs[i]("td:eq(0)").text(),
                        "marc_no": self.get_marc_no(
                            trs[i]("td:eq(1) a.blue").attr("href")
                        ),
                    }
                    for i in range(1, len(trs))
                ],
            }
            return {"code": 1000, "msg": "获取借阅列表成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取借阅列表超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取借阅列表时未记录的错误：" + str(e)}

    def get_borrow_history(self):
        """获取历史借阅列表"""
        url = urljoin(BASE_URL, "/reader/book_hist.php")
        try:
            req_history = self.sess.post(
                url,
                headers=self.headers,
                cookies=self.cookies,
                data={"para_string": "all"},
                timeout=TIMEOUT,
            )
            doc = pq(req_history.text)
            if doc("h5.box_bgcolor").text() == "登录我的图书馆":
                return {"code": 1006, "msg": "登录过期，请重新登录"}
            if str(doc(".iconerr")) != "":
                return {"code": 1005, "msg": "无历史借阅"}

            trs = list(doc("table tr").items())
            result = [
                {
                    "index": trs[i]("td:eq(0)").text(),
                    "title": trs[i]("td:eq(2) a.blue").text(),
                    "author": trs[i]("td:eq(3)").text(),
                    "location": trs[i]("td:eq(6)").text(),
                    "borrow_date": trs[i]("td:eq(4)").text(),
                    "return_date": trs[i]("td:eq(5)").text(),
                    "bar_code": trs[i]("td:eq(1)").text(),
                    "marc_no": self.get_marc_no(trs[i]("td:eq(2) a.blue").attr("href")),
                }
                for i in range(1, len(trs))
            ]
            return {"code": 1000, "msg": "获取历史借阅成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取历史借阅超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"获取历史借阅时未记录的错误：{str(e)}"}

    def get_pay_list(self):
        """获取账目清单"""
        url = urljoin(BASE_URL, "/reader/account.php")
        try:
            req_paylist = self.sess.post(
                url, headers=self.headers, cookies=self.cookies, timeout=TIMEOUT
            )
            doc = pq(req_paylist.text)
            if doc("h5.box_bgcolor").text() == "登录我的图书馆":
                return {"code": 1006, "msg": "登录过期，请重新登录"}
            if str(doc(".iconerr")) != "":
                return {"code": 1005, "msg": "无账目清单"}

            trs = list(doc("table tr").items())
            total = "".join(trs[len(trs) - 1]("td:eq(0)").text().strip().split())
            result = {
                "description": total[total.find(":") + 1 :][
                    : total[total.find(":") + 1 :].find("(")
                ],
                "items": [
                    {
                        "date": trs[i]("td:eq(0)").text().strip(),
                        "type": trs[i]("td:eq(1)").text().strip(),
                        "refund": trs[i]("td:eq(2)").text().strip(),
                        "contribution": trs[i]("td:eq(3)").text().strip(),
                        "pay_method": trs[i]("td:eq(4)").text().strip(),
                        "bill_no": trs[i]("td:eq(5)").text().strip(),
                    }
                    for i in range(1, len(trs) - 1)
                ],
            }
            return {"code": 1000, "msg": "获取账目清单成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取账目清单超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"获取账目清单时未记录的错误：{str(e)}"}

    def get_pay_detail(self):
        """获取欠款记录"""
        url = urljoin(BASE_URL, "/reader/fine_pec.php")
        try:
            req_paydetail = self.sess.post(
                url, headers=self.headers, cookies=self.cookies, timeout=TIMEOUT
            )
            doc = pq(req_paydetail.text)
            if doc("h5.box_bgcolor").text() == "登录我的图书馆":
                return {"code": 1006, "msg": "登录过期，请重新登录"}
            if str(doc(".iconerr")) != "" and "欠款记录为空" in str(doc(".iconerr")):
                return {"code": 1005, "msg": "无欠款记录"}
            table = doc("h2").text("欠款信息").next()
            trs = list(table("tr").items())
            result = [
                {
                    "title": trs[i]("td:eq(2)").text().strip(),
                    "author": trs[i]("td:eq(3)").text().strip(),
                    "location": trs[i]("td:eq(6)").text().strip(),
                    "borrow_date": trs[i]("td:eq(4)").text().strip(),
                    "due_date": trs[i]("td:eq(5)").text().strip(),
                    "marc_no": self.get_marc_no(trs[i]("td:eq(2) a").attr("href")),
                    "bar_code": trs[i]("td:eq(0)").text().strip(),
                    "call_no": trs[i]("td:eq(1)").text().strip(),
                    "payable": trs[i]("td:eq(7)").text().strip(),
                    "payin": trs[i]("td:eq(8)").text().strip(),
                    "state": trs[i]("td:eq(9)").text().strip(),
                }
                for i in range(1, len(trs))
            ]
            return {"code": 1000, "msg": "获取欠款信息成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取欠款信息超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"获取欠款信息时未记录的错误：{str(e)}"}

    def get_recommendation_books(self):
        url = urljoin(BASE_URL, "/top/top_lend.php?cls_no=ALL")
        try:
            req_popular = self.sess.get(url, headers=self.headers, timeout=TIMEOUT)
            doc = pq(req_popular.text)
            trs = list(doc("table.table_line tr").items())
            return {
                "code": 1000,
                "msg": "获取热门借阅成功",
                "data": {
                    "updated": int(time.time()),
                    "books": [
                        {
                            "index": trs[i]("td:eq(0)").text(),
                            "title": trs[i]("td:eq(1) a").text(),
                            "author": trs[i]("td:eq(2)").text(),
                            "publisher": trs[i]("td:eq(3)").text(),
                            "total_num": trs[i]("td:eq(5)").text(),
                            "borrowed_times": trs[i]("td:eq(6)").text(),
                            "borrowed_ratio": trs[i]("td:eq(7)").text(),
                            "marc_no": self.get_marc_no(
                                trs[i]("td:eq(1) a").attr("href")
                            ),
                            "call_no": trs[i]("td:eq(4)").text(),
                        }
                        for i in range(1, len(trs))
                    ],
                },
            }
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取热门借阅超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"获取热门借阅时未记录的错误：{str(e)}"}

    def search_book(self, type, content: str, page: int):
        """
        搜索图书
        type: 书名-title 作者-author 主题词-keyword ISBN/ISSN-isbn 订购号-asordno 分类号-coden 索书号-callno 出版社-publisher 丛书名-series
        """
        url = urljoin(BASE_URL, "/opac/openlink.php")
        try:
            data = {
                "onlylendable": "yes",
                type: content,
                "page": page,
            }
            req_search = self.sess.get(
                url, headers=self.headers, params=data, timeout=TIMEOUT
            )
            doc = pq(req_search.text)
            container = doc("div#container")
            count = container("strong.red").text()
            search_list = container("ol#search_book_list").items("li")
            total_page = container("span.num_prev b font[color='black']").text()
            pages = int(total_page) if total_page != "" else 1
            if page > pages:
                return {"code": 999, "msg": "已超过最多页数"}

            result = {
                "type": type,
                "content": content,
                "count": count,
                "page": page,
                "pages": pages,
                "books": [
                    {
                        "type": i("h3 span").text(),
                        "title": i("h3 a").text()[i("h3 a").text().find(".") + 1 :],
                        "author": re.findall(r"span>(.*)<", str(i("p")))[1].strip(),
                        "publisher": "".join(
                            re.findall(r"(.*) <br/>&#13", str(i("p")))[2]
                            .strip()
                            .split()
                        ),
                        "total_num": re.findall(r"馆藏复本：(\d+)", str(i("p")))[0],
                        "loanable_num": re.findall(r"可借复本：(\d+)", str(i("p")))[0],
                        "marc_no": self.get_marc_no(i("p a").attr("href")),
                        "call_no": re.findall(r"</a>(.*)</h3>", str(i("h3")))[
                            0
                        ].strip(),
                    }
                    for i in search_list
                ],
            }
            return {"code": 1000, "msg": "搜索图书成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "搜索图书超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": f"搜索图书时未记录的错误：{str(e)}"}

    def get_book_detail(self, marc_no: str):
        """获取图书详情"""
        url = urljoin(BASE_URL, "/opac/item.php")
        data = {"marc_no": marc_no}
        try:
            req_detail = self.sess.get(
                url, headers=self.headers, params=data, timeout=TIMEOUT
            )
            doc = pq(req_detail.text)
            details = doc("#item_detail dl").items()
            trs = list(doc("table#item tr").items())
            result = {}
            for i in details:
                if "题名/责任者" in i("dt").text():
                    result["title"] = i("dd a").text()
                    result["full_title"] = i("dd").text()
                elif "其它题名" in i("dt").text():
                    result["oth_title"] = i("dd").text()
                elif "个人责任者" in i("dt").text():
                    result["author"] = i("dd").text()
                elif "个人次要责任者" in i("dt").text():
                    result["oth_author"] = i("dd").text()
                elif "学科主题" in i("dt").text():
                    result["category"] = i("dd").text()
                elif "出版发行项" in i("dt").text():
                    result["publisher"] = i("dd").text()
                elif "ISBN及定价" in i("dt").text():
                    result["isbn"] = i("dd").text()
                elif "载体形态项" in i("dt").text():
                    result["physical"] = i("dd").text()
                elif "一般附注" in i("dt").text():
                    result["notes"] = i("dd").text()
                elif "责任者附注" in i("dt").text():
                    result["author_notes"] = i("dd").text()
                elif "提要文摘附注" in i("dt").text():
                    result["abstract"] = i("dd").text()
                elif "中图法分类号" in i("dt").text():
                    result["call_no"] = i("dd").text()
            result["books"] = [
                {
                    "annual_roll": "".join(trs[n]("td:eq(2)").text().split()),
                    "location": trs[n]("td:eq(3)").text().strip(),
                    "return_location": trs[n]("td:eq(3)").attr("title"),
                    "status": trs[n]("td:eq(4)").text(),
                    "bar_code": trs[n]("td:eq(1)").text(),
                    "call_no": trs[n]("td:eq(0)").text(),
                }
                for n in range(1, len(trs))
            ]
            return {"code": 1000, "msg": "获取图书详情成功", "data": result}
        except exceptions.Timeout:
            return {"code": 1003, "msg": "获取图书详情超时"}
        except (
            exceptions.RequestException,
            json.decoder.JSONDecodeError,
            AttributeError,
        ):
            traceback.print_exc()
            return {"code": 2333, "msg": "连接错误：图书馆系统可能无法正常访问"}
        except Exception as e:
            traceback.print_exc()
            return {"code": 999, "msg": "获取图书详情时未记录的错误：" + str(e)}

    @classmethod
    def encode_password(cls, sca, password):
        encode_password = ""
        for i in range(len(password)):
            try:
                num0 = sca.index(password[i])
            except:
                num0 = -1
            if num0 == -1:
                code = ord(password[i])
                code = hex(code)[2:]
            else:
                code = sca[(num0 + 3) % 62]
                code = hex(ord(code))[2:]
            num1 = int(random.random() * 62)
            num2 = int(random.random() * 62)
            encode_password += str(sca[num1]) + str(code) + str(sca[num2])
        return encode_password

    @classmethod
    def check_password(cls, password):
        if len(password) < 8 and len(password) >= 12:
            return False
        if bool(re.search(r"\d", password)) == False:
            return False
        if any(x.isupper() for x in password) == False:
            return False
        if any(x.islower() for x in password) == False:
            return False
        return True

    @classmethod
    def get_marc_no(cls, content):
        marc_no = re.findall(r"marc_no=(.*)", content)
        if not marc_no:
            return None
        return marc_no[0]
