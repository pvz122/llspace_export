# llspace接口文档

## Header

| Header | 值来源 | 示例值 | 是否必需 |
|--------|--------|--------|----------|
| `salt` | 当前时间戳（`System.currentTimeMillis()`）的 MD5 | `a1b2c3d4e5f6...` | 是 |
| `sign` | 固定字符串 + token（如有）+ salt 的 MD5 → 再转大写 | `ABCDEF123456...` | 是 |
| `CLIENT-VERSION` | 固定字符串 `"1222"` | `1222` | 是 |
| `PLATFORM` | 固定字符串 `"ard"` | `ard` | 是 |
| `Authorization` | 仅当已登录（`strA` 非空）时添加 | `xxx` | 登录时不需要 |

Python 生成 Header 示例：

```python
import time
import hashlib
import base64

def md5(s: str) -> str:
    """计算字符串的 MD5（32位小写）"""
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def generate_headers(token: str = None) -> dict:
    """
    生成符合 App 要求的 HTTP Headers
    
    :param token: 登录后的 Authorization 值（Base64(user_id:token)）
                  如果为 None 或空字符串，则视为未登录（如登录请求）
    :return: Headers 字典
    """
    # 1. 生成 salt = md5(当前毫秒时间戳)
    timestamp_ms = str(int(time.time() * 1000))
    salt = md5(timestamp_ms)
    
    # 2. 构造 sign 的 base 字符串
    secret_key = "C6DAA093BF4C08B46F01FAE4F09B797A"
    if token and token.strip():
        # 已登录：secret + token + salt
        base_str = secret_key + token + salt
    else:
        # 未登录（如登录请求）：secret + salt
        base_str = secret_key + salt
    
    # 3. 生成 sign = MD5(base_str).upper()
    sign = md5(base_str).upper()
    
    # 4. 构建 headers
    headers = {
        "salt": salt,
        "sign": sign,
        "CLIENT-VERSION": "1222",
        "PLATFORM": "ard"
    }
    
    # 5. 如果 token 有效，添加 Authorization
    if token and token.strip():
        headers["Authorization"] = token
    
    return headers
```

## Interface List

API 服务器为 `https://api.llspace.com`

### 用户登录

`POST /api/1/users/sign_in`

- 参数：form - `String account`, `String password`
- 返回值：
```json
{
    "code": 0,
    "message": "",
    "user": {
        "authentication_token": "<SECRET TOKEN>",
        "accounts": [
            {
                "title": "邮箱地址",
                "key": "email",
                "hasbind": 1,
                "name": "<SECRET EMAIL>"
            },
            {
                "title": "手机号码",
                "key": "mobile",
                "hasbind": 1,
                "name": "<SECRET MOBILE>"
            },
            {
                "title": "微信帐号",
                "key": "wechat",
                "hasbind": 1,
                "name": "<SECRET WECHAT>"
            },
            {
                "title": "新浪微博",
                "key": "weibo",
                "hasbind": 0,
                "name": ""
            }
        ],
        "passport": {
            "has_passport": 0,
            "passport_pg_id": 0,
            "purchase_time": ""
        },
        "premium": {
            "expired_date": 1795795199,
            "recruit_available_count": 8,
            "premium_status": 1
        },
        "has_password": 1,
        "identity_type": 1,
        "avatar_normal_url": "https://assets.llspace.com/avatars/41/2c/1363ac/normal-25c734af8e2e6243c840f0a151ddf0fd.jpg",
        "avatar_url": "https://assets.llspace.com/avatars/41/2c/1363ac/normal-25c734af8e2e6243c840f0a151ddf0fd.jpg",
        "description": "The ocean washed over your grave.",
        "gender": 1,
        "id": 1270700,
        "name": "Pierre",
        "stars": 2329,
        "birthday": "0000-11-22",
        "age_type": "0",
        "gender_type": "0",
        "distance_type": "0",
        "priority_type": "4"
    }
}
```

### 获取包列表

`POST /api/1/pg/list`

- 参数：无
- 返回值：
```json
{
    "code": 0,
    "message": "",
    "pg": [
        {
            "category": 1,
            "pg_id": 6607067,
            "pg_name": "絮说",
            "pg_type": -1,
            "cover_url": "https://imagenew.llspace.com/pg_covers/13/5b/64d0db/5a0aaf729c2127122d3f667c2d2ed40c4481.jpg",
            "tidy_flag": 2,
            "creator_id": 1270700,
            "status": 1,
            "event_type": 1,
            "chained_url": "",
            "c_num": 14,
            "image_url": "",
            "member_count": 1,
            "permit_status": 1,
            "notify_status": 2,
            "accept_status": 2,
            "text": "说说说说说",
            "text_align": 2,
            "share": {
                "share_title": "《絮说》",
                "share_des": "Pierre在平行世界里写的一本书...",
                "share_url": "https://www.llspace.com/g-main-6607067.html",
                "share_photo": "https://imagenew.llspace.com/pg_covers/13/5b/64d0db/5a0aaf729c2127122d3f667c2d2ed40c4481.jpg"
            }
        },
        {
            "category": 1,
            "pg_id": 6607654,
            "pg_name": "捡阅",
            "pg_type": -1,
            "cover_url": "https://imagenew.llspace.com/pg_covers/62/26/64d326/7a995d7ca96bb5ce969ceb47623fde4a9576.jpg",
            "tidy_flag": 2,
            "creator_id": 1270700,
            "status": 1,
            "event_type": 1,
            "chained_url": "",
            "c_num": 7,
            "image_url": "",
            "member_count": 1,
            "permit_status": 1,
            "notify_status": 2,
            "accept_status": 2,
            "text": "读读读",
            "text_align": 2,
            "share": {
                "share_title": "《捡阅》",
                "share_des": "Pierre在平行世界里写的一本书...",
                "share_url": "https://www.llspace.com/g-main-6607654.html",
                "share_photo": "https://imagenew.llspace.com/pg_covers/62/26/64d326/7a995d7ca96bb5ce969ceb47623fde4a9576.jpg"
            }
        },
        {
            "category": 1,
            "pg_id": 6607072,
            "pg_name": "惶然录",
            "pg_type": -1,
            "cover_url": "https://imagenew.llspace.com/pg_covers/18/60/64d0e0/f94e3c78211d8055bf282d83e673c04a2218.jpg",
            "tidy_flag": 2,
            "creator_id": 1270700,
            "status": 1,
            "event_type": 1,
            "chained_url": "",
            "c_num": 6,
            "image_url": "",
            "member_count": 1,
            "permit_status": 1,
            "notify_status": 2,
            "accept_status": 2,
            "text": "此时我面对晚霞开始出神。",
            "text_align": 2,
            "share": {
                "share_title": "《惶然录》",
                "share_des": "Pierre在平行世界里写的一本书...",
                "share_url": "https://www.llspace.com/g-main-6607072.html",
                "share_photo": "https://imagenew.llspace.com/pg_covers/18/60/64d0e0/f94e3c78211d8055bf282d83e673c04a2218.jpg"
            }
        },
        {
            "category": 1,
            "pg_id": 6607073,
            "pg_name": "涣然录",
            "pg_type": -1,
            "cover_url": "https://imagenew.llspace.com/pg_covers/19/61/64d0e1/cb0c3e1a5f104656f6b1f852432f3d9c6541.jpg",
            "tidy_flag": 2,
            "creator_id": 1270700,
            "status": 1,
            "event_type": 1,
            "chained_url": "",
            "c_num": 7,
            "image_url": "",
            "member_count": 1,
            "permit_status": 1,
            "notify_status": 2,
            "accept_status": 2,
            "text": "因为多有智慧，就多有愁烦；加增知识的，就加增忧伤。",
            "text_align": 1,
            "share": {
                "share_title": "《涣然录》",
                "share_des": "Pierre在平行世界里写的一本书...",
                "share_url": "https://www.llspace.com/g-main-6607073.html",
                "share_photo": "https://imagenew.llspace.com/pg_covers/19/61/64d0e1/cb0c3e1a5f104656f6b1f852432f3d9c6541.jpg"
            }
        },
        {
            "category": 20,
            "pg_id": 6200280,
            "pg_name": "Pierre的沙龙包",
            "pg_type": 10200,
            "cover_url": "https://assets.llspace.com/pg_covers/0000/custom-pgBg10200@2x.png",
            "tidy_flag": 1,
            "creator_id": 1270700,
            "status": 1,
            "event_type": 3,
            "chained_url": "",
            "c_num": 0,
            "image_url": "",
            "member_count": 1,
            "permit_status": 1,
            "notify_status": 2,
            "accept_status": 2,
            "text": "",
            "text_align": 2,
            "share": {
                "share_title": "沙龙卡包",
                "share_des": "认识自己，思考，成长，遇见伙伴……",
                "share_url": "https://www.llspace.com/g-main-6200280.html",
                "share_photo": "https://assets.llspace.com/pg_covers/0000/custom-pgBg10200@2x.png"
            },
            "extras": {
                "salon_period_date": "2023.02-2024.02",
                "updated_status": 0
            }
        }
    ],
    "user": {
        "xxx": "yyy"
    }
}
```

### 获取包内卡片列表

`POST /api/1/pg/directoryList`

- 参数：form - `long pg_id`
- 返回值：
```json
{
    "code": 0,
    "message": "",
    "cards": [
        {
            "id": 15641247,
            "card_cat": 11,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.31",
                "created_date": "2025.12.31",
                "public_status": 1,
                "created_int": 1767113663
            }
        },
        {
            "id": 15634230,
            "card_cat": 10,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.21",
                "created_date": "2025.12.21",
                "public_status": 1,
                "created_int": 1766295817
            }
        },
        {
            "id": 11619446,
            "card_cat": 4,
            "owner": {
                "user_id": 106
            },
            "data": {
                "title": "冬至",
                "created_date": "2019.1.28",
                "public_status": 1,
                "created_int": 1548668536
            }
        },
        {
            "id": 15629669,
            "card_cat": 1,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.14",
                "created_date": "2025.12.14",
                "public_status": 1,
                "created_int": 1765724760
            }
        },
        {
            "id": 15628302,
            "card_cat": 1,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.12",
                "created_date": "2025.12.13",
                "public_status": 1,
                "created_int": 1765557519
            }
        },
        {
            "id": 15627237,
            "card_cat": 11,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.11",
                "created_date": "2025.12.11",
                "public_status": 1,
                "created_int": 1765447659
            }
        },
        {
            "id": 15624722,
            "card_cat": 10,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.7 兼论我父母如何生活",
                "created_date": "2025.12.8",
                "public_status": 1,
                "created_int": 1765125717
            }
        },
        {
            "id": 15623924,
            "card_cat": 1,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.6",
                "created_date": "2025.12.7",
                "public_status": 1,
                "created_int": 1765037624
            }
        },
        {
            "id": 15621250,
            "card_cat": 1,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.12.2",
                "created_date": "2025.12.3",
                "public_status": 1,
                "created_int": 1764696374
            }
        },
        {
            "id": 15619739,
            "card_cat": 1,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.11.30",
                "created_date": "2025.11.30",
                "public_status": 1,
                "created_int": 1764518307
            }
        },
        {
            "id": 15619002,
            "card_cat": 10,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.11.29",
                "created_date": "2025.11.29",
                "public_status": 1,
                "created_int": 1764431100
            }
        },
        {
            "id": 15618325,
            "card_cat": 10,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.11.28",
                "created_date": "2025.11.28",
                "public_status": 1,
                "created_int": 1764344949
            }
        },
        {
            "id": 15617740,
            "card_cat": 1,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "日记 25.11.27",
                "created_date": "2025.11.28",
                "public_status": 1,
                "created_int": 1764262907
            }
        },
        {
            "id": 15617730,
            "card_cat": 10,
            "owner": {
                "user_id": 1270700
            },
            "data": {
                "title": "我回来",
                "created_date": "2025.11.28",
                "public_status": 1,
                "created_int": 1764261513
            }
        }
    ]
}
```


### 获取卡片详情

`POST /api/1/cards/detail`

- 参数：form - `long card_id`, `long from_pg_id`
- 返回值：
```json
{
    "code": 0,
    "unread": 0,
    "card": {
        "id": 15634230,
        "title": "日记 25.12.21",
        "url": "https://www.llspace.com/v/83fb6973",
        "short_des": "一觉醒来喉咙发炎变成气泡音了。还是决定去赴约，可是茗把我鸽了。茗总是可以毫无歉意...",
        "cover_url": "https://imagenew.llspace.com/card_covers/16/36/ee8f36/retina-e1a8188c1a652b5beb379b0ae841996b.jpg",
        "share_des": "一觉醒来喉咙发炎变成气泡音了。还是决定去赴约，可是茗把我鸽了。茗总是可以毫无歉意...",
        "share_title": "《日记 25.12.21》",
        "created_date": "2025.12.21",
        "updated_int": 1766307203,
        "stars": 0,
        "public_status": 1,
        "owner_id": 1270700,
        "owner_name": "Pierre",
        "owner_gender": 1,
        "owner_avatar": "https://assets.llspace.com/avatars/41/2c/1363ac/medium-25c734af8e2e6243c840f0a151ddf0fd.jpg",
        "description": "一觉醒来喉咙发炎变成气泡音了。还是决定去赴约，可是茗把我鸽了。茗总是可以毫无歉意地这样做。\n\n自小时候那次后，就再也没来过故宫，这次见到真是印象深刻。\n\n皇帝坐在重重围墙的中央，指挥着巨大的帝国。他的声音只在第一重围墙内听见，人们不得不不停四处奔跑，转述他的话语。就算这样，他的指令也至多传到京城的边墙。对其它地方的人们而言，皇帝是一种想象。他们热衷于在墙上画满繁复的图案，龙、虎、貔恘。他们把石头和木头垒在一起，形成各种样式。他们装饰围墙，从京城到帝国边疆。他们在围墙上幻想他们的皇帝。但那个人从来没有离开第一堵墙，他不晓得墙外有何物。他白天向围墙发号施令，晚上对着围墙幻想一个帝国。\n\n故宫的百年展实在诚意不够，稍有点分量的都是仿制品。",
        "card_cat": 10,
        "created_int": 1766295817,
        "card_cat_style": 10,
        "b_pgs": [],
        "sent_stars": 0,
        "fav_num": 0,
        "description_align": 1,
        "title_align": 2,
        "text_color_type": 1,
        "icon_type": 1,
        "theme_color": "00000A",
        "pg_id": 6607067,
        "collect_property": 1,
        "owner_package": {
            "category": 1,
            "pg_id": 6607067,
            "pg_name": "絮说",
            "pg_type": -1,
            "cover_url": "https://imagenew.llspace.com/pg_covers/13/5b/64d0db/5a0aaf729c2127122d3f667c2d2ed40c4481.jpg",
            "tidy_flag": 2,
            "creator_id": 1270700,
            "status": 1,
            "event_type": 1,
            "chained_url": ""
        }
    }
}
```
