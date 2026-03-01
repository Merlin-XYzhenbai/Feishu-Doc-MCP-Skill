# 个人使用 MCP 服务

飞书远程 MCP 服务，是经过官方精心打造的“AI 连接器”，让你的 AI 客户端直接变身为强大的飞书助理，安全、稳定且高效。
当前支持「**云文档**」场景，查看[支持的 MCP 工具集](https://open.larkoffice.com/document/mcp_open_tools/supported-tools)，后续会开放更多场景（如多维表格、日历）。欢迎[反馈](https://bytedance.larkoffice.com/share/base/form/shrcnGy0YNaviYYLjAX8zMqIW3f)您的使用场景 🥳

## 步骤一：创建 MCP 远程服务

你可以通过生成一个专属的 MCP 远程服务链接，即可安全地授权 AI 客户端访问您的飞书数据。

1. 登录[飞书 MCP 配置平台](https://open.feishu.cn/page/mcp)。warning
   远程 MCP Server 配置功能正在内测中，如无法访问配置平台，可在文档页面右下角联系技术支持（选择 **展开 ![1.jpeg](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/3a8c96a3a2e51904a7844aa528bef4e9_Fl5jtZzjjW.jpeg?height=118&lazyload=true&maxWidth=25&width=88) > 技术支持 ![2.jpeg](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/f4fdf13e08e57688862cc2e94e327d9f_1wOZUmukkM.jpeg?height=126&lazyload=true&maxWidth=28&width=126)**）。
2. 在页面左侧，点击 **创建 MCP 服务**。
3. 在 **MCP 工具配置** 区域，确认当前用户身份。
   后续使用 MCP 服务时，都会以当前显示的用户身份访问和操作飞书数据，因此，需确认当前用户身份正确，否则需使用正确的用户重新登录。![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/e7bfdbe62f8d2e2ec417ab8d216d1c82_Zqr5FEaZPw.png?height=628&lazyload=true&maxWidth=450&width=1654)
4. 在 **添加工具** 卡片内，点击 **添加**，在添加工具对话框，选择「**云文档**」工具集。
   当前支持「**云文档**」场景，后续会开放更多业务场景，查看[已支持的 MCP 工具集](https://open.larkoffice.com/document/mcp_open_tools/supported-tools)。
5. 点击 **确认添加**，并在弹出的 **获取用户授权** 对话框，确认授权用户登录信息、飞书 MCP 应用获得的权限信息后，点击 **授权**。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/b90b7f81ba9ca46b59fcff96e34167c4_G7hptzWYik.png?height=1242&lazyload=true&maxWidth=300&width=1256)

4. 添加工具后，在 **如何使用 MCP 服务** 区域，查看 **服务器 URL、JSON**。warning
   服务器 URL 代表以当前登录用户身份去调用飞书工具，相当于个人密钥，**请勿泄露给其他人**。
   ![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/46d643e6d2ef5e0e8a69742f273644ba_DIszsZcNeH.png?height=626&lazyload=true&maxWidth=400&width=1642)

- 自2026年2月24日起，新创建的飞书 MCP 服务有效期缩短为 7 天，过期自动失效，如需延长有效期，可点击 **重新授权**。
  - 如担心链接已泄露，可点击 **重置链接**，使当前的 URL 失效，并生成一个新的 URL。
  - **传输方式** 保持默认 Streamable HTTP 即可。Streamable HTTP 是基于 HTTP 协议的分块（chunked）流式传输，支持任意格式数据（如文件、日志）的渐进式传输。

## 步骤二：一键安装到 TRAE\Cursor\VS Code

平台在 MCP 服务页面底部提供了快捷添加到 TRAE、Cursor、VS Code 的入口，供你一键快速安装。
该方式需要确保本地已安装 **最新版本** 的 [TRAE](https://www.trae.cn/)、[Cursor](https://cursor.com/) 或 [VS Code](https://code.visualstudio.com/download)。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/1a73ba247e10cde93b40f6856f6f42d9_nIcefqXAHP.png?height=832&lazyload=true&maxWidth=400&width=1634)

| 客户端            | 安装步骤                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **TRAE**    | 1.点击**添加到 TRAE**，并根据指引打开 TRAE 客户端。 `<br>`2. 在 TRAE 的 MCP 手动配置对话框内，点击 **确认**。`<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/f8f371870fe24bfabf47fc8be9209393~tplv-goo7wpa0wc-image.image?height=888&lazyload=true&maxWidth=320&width=1050)`<br>`3. 点击 MCP 路径，查看已成功配置的飞书 MCP Server。 `<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/79ea2acf7fb24037bdcf3f5cca1231fe~tplv-goo7wpa0wc-image.image?height=830&lazyload=true&maxWidth=320&width=1484)`<br>`4. 因飞书工具较多，为避免超出 TRAE 上下文限制，建议**创建智能体并按需选择工具**。配置完成后，输入场景提示词并发送，等待 AI 响应即可。 `<br>`![trae1.gif](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/2552ea5793cceaeaa25d51b38ed5fccc_sdshQTMvGU.gif?height=1034&lazyload=true&maxWidth=380&width=2006)                                                                                                                                                                                                                                                         |
| **Cursor**  | 1.点击**添加到 Cursor**，并根据指引打开 Cursor 客户端。 `<br>`2. 在 Cursor 的 MCP Server 安装对话框内，点击 **安装**。 `<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/be026ddb1d264bc4af37739f2ab0ed36~tplv-goo7wpa0wc-image.image?height=484&lazyload=true&maxWidth=320&width=1078)`<br>`**注意事项**：![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/35492debcdf346e9b7695d3691be469d~tplv-goo7wpa0wc-image.image?height=170&lazyload=true&maxWidth=320&width=1110)`<br>`3. 可打开控制台，在 output 页签下查看当前 MCP server 处于成功连接的运行状态。 `<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/beddb1e385bb4404ac8fa51552dbfe4c~tplv-goo7wpa0wc-image.image?height=868&lazyload=true&maxWidth=320&width=1752)`<br>`4. 在右侧 AI 对话框中输入提示词，即可使用飞书 MCP 服务。 `<br><md-alert>`Cursor 版本更新可能会导致工具调用截断，官方修复版正灰度发布中。`<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/0799f1a854f9468aa4b2e13ab45f77a4~tplv-goo7wpa0wc-image.image?height=224&lazyload=true&maxWidth=320&width=1498) |
| **VS Code** | 1.点击**添加到 VS Code**，并根据指引打开 VS Code 客户端。`<br>`2. 在 VS Code 的 MCP 安装对话框内，点击 **安装**。 `<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/c3f816b9a40148a597c0ae942097221f~tplv-goo7wpa0wc-image.image?height=704&lazyload=true&maxWidth=320&width=1642)`<br>`3. 安装后，点击管理图标 > **显示输出** 或 **显示配置 JSON**，即可查看 MCP server 当前正在运行状态。 `<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/fa5d93523de94c3fa987f6bc63e84518~tplv-goo7wpa0wc-image.image?height=896&lazyload=true&maxWidth=320&width=1828)`<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/899cdf52d9c14c38a29417ceccff0f08~tplv-goo7wpa0wc-image.image?height=1442&lazyload=true&maxWidth=320&width=2070)`<br>`4. 在右侧 AI 对话框中输入提示词，即可使用飞书 MCP 服务。 `<br>`![alt text](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/e7d5a7b663a648a0934bbe6edb4ffed2~tplv-goo7wpa0wc-image.image?height=270&lazyload=true&maxWidth=320&width=1132)                                                                        |

### （可选）安装到其他 AI 客户端

1. 在[飞书 MCP 配置平台](https://open.feishu.cn/page/mcp) 中，复制已创建的 MCP 服务的 **服务器 URL\JSON**。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/46d643e6d2ef5e0e8a69742f273644ba_DIszsZcNeH.png?height=626&lazyload=true&maxWidth=400&width=1642)

2. 参考以下常见 AI 客户端的官方文档将复制的 MCP 地址配置到对应的 AI 客户端上：

- **Claude Code**：[Claude Code 官方文档](https://code.claude.com/docs/en/mcp#installing-mcp-servers)
  - **Gemini CLI**：[Gemini CLI 官方文档](https://geminicli.com/docs/tools/mcp-server/#how-to-set-up-your-mcp-server)
  - **n8n**：[n8n 官方文档](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolmcp/)
  - **Windsurf**：[Windsurf 官方文档](https://docs.windsurf.com/zh/plugins/cascade/mcp)

# 常见问题

## 如何重命名或删除已配置的 MCP Server？

1. 登录[飞书 MCP 配置平台](https://open.feishu.cn/page/mcp)。
2. 在左侧 **已创建的 MCP 服务** 列表，选择需要操作的服务。
3. 在标题区域，点击 **···**，可选择 **重命名** 或 **删除** 当前服务。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/41d0115ec494780bac58c73255a6f1d8_apiZDVonlS.png?height=340&lazyload=true&maxWidth=500&width=1888)

## 配置工具后，如何修改？修改后是否需要重新生成服务器 URL？

1. 登录[飞书 MCP 配置平台](https://open.feishu.cn/page/mcp)。
2. 在左侧 **已创建的 MCP 服务** 列表，选择需要操作的服务。
3. 在 **MCP 工具配置** 区域的 **添加工具** 卡片内，点击 **编辑**，修改已选择的工具，并保存即可。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/c04e449a3fa05a63dd56fd8519889a27_OnAAhC67PB.png?height=455&lazyload=true&maxWidth=400&width=1280)

4. 修改后，需要在 AI 工具内刷新或重启 MCP 服务。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/6cafff6b75ef6c7774ad5e7e1555425b_rTKtYX9ztd.png?height=428&lazyload=true&maxWidth=400&width=988)

## Cursor 内的 MCP Tools 状态显示异常是什么原因？

- **问题现象**：如下图，将 MCP 服务一键安装到 Cursor 后，工具状态指示灯显示为红色。

![image.png](//sf3-cn.feishucdn.com/obj/open-platform-opendoc/5c4b9dd980e06486e6ee56548db5b590_3robuSsacv.png?height=170&lazyload=true&maxWidth=400&width=1110)

- **解决方案**：可忽略该状态，直接在 AI Chat 中发送需求，根据 AI 响应结果判断是否可以正常调用飞书 MCP 工具，如果可以即没有问题。如果无法调用，请重新配置远程 MCP 服务并一键安装到 Cursor 后重试。

## 使用 MCP 访问文档时有哪些权限规则？

与当前使用 MCP 服务的用户自身所拥有的云文档权限完全一致，MCP 服务没有设置其他权限规则。
