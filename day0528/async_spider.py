import asyncio
import aiohttp

async def fetch(url, session):
    async with session.get(url, timeout=10) as resp:
        html = await resp.text()
        print(f"{url}抓取完成，长度：{len(html)}")
        return html
    
async def main():
    urls = [
        "https://www.baidu.com",
        "https://www.bing.com",
        "https://www.python.org"
    ]

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]
        await asyncio.gather(*tasks)

if __name__ =="__main__":
    asyncio.run(main())