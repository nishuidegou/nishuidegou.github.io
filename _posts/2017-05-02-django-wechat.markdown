---
layout: post
title:  "django 微信"
date:   2017-05-02 10:23:48 +0800
categories: python web
---
想用django做微信公众号后端。把学习的重点记录一下：

测试过程中出现了几个问题：

1.django setting中的时区与Ubuntu的时区不一致

2.验证token时出现的sort()错误，request.GET.get("signature", None)改为request.GET.get("signature", '')

3.hashlib.sha1验证时出现的编码错误，tmp_str = hashlib.sha1(tmp_str.encode('utf-8')).hexdigest()

4.参考官方文档对POST进行回复，其中出现了“该公众号暂时无法提供服务，请稍后再试”

{% highlight python %}
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest
import hashlib
from lxml import etree
from django.utils.encoding import smart_str
from django.views.decorators.csrf import csrf_exempt

# import xml.etree.ElementTree as ET
# import time
import wechat.reply as reply
import wechat.receive as receive

# Create your views here.

@csrf_exempt
def wechat(request):
    if request.method == "GET":
        signature = request.GET.get("signature", '')
        timestamp = request.GET.get("timestamp", '')
        nonce = request.GET.get("nonce", '')

        echostr = request.GET.get("echostr", '')
        token = 'YOUR TOKEN'

        tmp_list = [token, timestamp, nonce]
        tmp_list.sort()
        tmp_str = ''.join([s for s in tmp_list])
        tmp_str = hashlib.sha1(tmp_str.encode('utf-8')).hexdigest()

        if tmp_str == signature:
            return HttpResponse(echostr)
        else:
            return HttpResponseBadRequest("Verify Failed")

    elif request.method == "POST":
        rawStr = smart_str(request.raw_post_data)
        recMsg = receive.parse_xml(rawStr)
        if isinstance(recMsg, receive.Msg) and recMsg.MsgType == 'text':
            toUser = recMsg.FromUserName
            fromUser = recMsg.ToUserName
            content = "test"
            replyMsg = reply.TextMsg(toUser, fromUser, content)

            return HttpResponse(replyMsg.send())
        else:
            return HttpResponse("success")

{% endhighlight %}



微信平台 [官方指导][官方指导]

[官方指导]:https://mp.weixin.qq.com/wiki?action=doc&id=mp1472017492_58YV5&t=0.2930851544781329#2

