import time
import nodriver as uc
import os
import json
import re
import logging
import mysql.connector
from pathlib import Path
#NDAJKSDNKJAS

DEBUG = True

async def main():
    first_run = False
    user_data_dir = os.path.join(os.getcwd(), "profile")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        first_run = True
    chrome_dir = os.path.join(os.getcwd(), "Chrome\\Application\\chrome.exe")
    driver = await uc.start(user_data_dir=user_data_dir, browser_executable_path=chrome_dir)
    tab = await driver.get("https://shopee.vn/search?keyword=gi%C3%A0y%20nam")
    if first_run:
        print("Please Login to Shopee in the opened browser window.")
        print("Press Enter after you have logged in...")
        input()
    await tab
    #await tab.set_window_state(5000, 5000, 1920, 1080, 'normal')
    #await tab.set_window_state(5000, 5000, 1920, 1080, 'normal')
    log.info('Getting products...')
    log.debug('wait for products to load...')
    
    while(True):
        e = await tab.select(".shopee_ic", timeout=60)
        tmp = await e.query_selector('a')
        if (tmp and tmp.attrs.href):
            log.debug(f'test tmp: {tmp.attrs.href}')
            break
        else:
            log.debug("tmp is none, wait...")
            await tab.scroll_down(1000)
            time.sleep(1)
            
    [await tab.scroll_down(1000) for _ in range(3)]
    
    time.sleep(1)
        
    log.debug("get all products...")
    links = await tab.evaluate("""
(() => {
    let ret = []
    document.querySelectorAll('.shopee_ic').forEach((e)=>{
        let b = e.querySelector('a')
        console.log(b)
        if (b)
        ret.push( e.querySelector('a').href)
    })
    return ret  
})()""")
    links = parse_string_arr(links)
    log.info(f"Found {len(links)} link")
    for i, link in enumerate(links, 1):
        log.info(f'Processing {i}/{len(links)}')
        log.debug(f'open link: {link}')
        try:
            product_info = await get_product_info(tab, link)
        except Exception as e:
            log.exception(f'exception when getting product info: {e}')
            time.sleep(1)
            continue
        if product_info is None:
            time.sleep(1)
            continue
        try:
            write_object_to_json(product_info)
            log.info(f'Done product: {product_info["title"]}')
        except Exception as e:
            log.exception(f'exception when writing json: {e}')
            log.debug(f'object: {product_info}')
        finally:
            time.sleep(1)
    driver.stop()
    
    

async def get_product_info(tab: uc.Tab, link):
    await tab.get(link)
    await tab
    
    a = await tab.select('.page-product', 60)
    time.sleep(1)
    
    [await tab.scroll_down(1000) for _ in range(3)]
        
    await tab
    time.sleep(2)
    title = await a.query_selector('h1')
    title = title.text_all
    
    if skip_product(title):
        log.info(f'Skipping product: {title} -> {get_file_name(title)}.json already exists')
        return None
    
    no_sold = await a.query_selector('section:nth-child(2)>section:nth-child(2)>div>div:nth-child(2)>div')
    no_sold = no_sold.text_all
    cmt_list = []
    while (True):
        log.debug('Loading comments...')
        tmp_cmt_list = await tab.evaluate("""
(() => {
    let ret = []
    let cmt_list = document.querySelectorAll('.shopee-product-comment-list>div')
    cmt_list.forEach(cmt => {
        let main_content = cmt.querySelector('div:nth-child(2)')
        let cmt_text = ''
        let cmt_text_container = main_content.children[1]
        if (cmt_text_container.querySelector('div.rating-media-list') === null && cmt_text_container.querySelector('div.shopee-product-rating__actions') === null){
            cmt_text = cmt_text_container.innerText.trim()
        }
        let username_and_rating = main_content.children[0]
        let username = username_and_rating.firstChild.innerText.trim()
        let rating = username_and_rating.children[1].querySelectorAll('svg.icon-rating-solid').length
        let meta = username_and_rating.children[2].innerText.trim()
        ret.push({
            'username': username,
            'metadata': meta,
            'rating': rating,
            'comment': cmt_text
        })
    })
    return ret
})()
           
""")
        tmp_cmt_list = unpack_to_dict(tmp_cmt_list)
        cmt_list.extend(tmp_cmt_list)
        log.debug(f'got {len(cmt_list)} comments!')
        # log.debug(f'{tmp_cmt_list = }')
        log.debug('try to load more comments...')
        status = await tab.evaluate("""
(() => {
let next_btn = document.querySelector('.product-ratings__page-controller').querySelector('.shopee-button-solid+button')
// check if next_btn is a number button
console.log(next_btn)
if (!isNaN(parseInt(next_btn.innerText))) {
    next_btn.click()
} else return false
return true
})()

""")
        if (not status):
            log.debug('no more comments!')
            break
        
        error = False
        while(True):
            # log.debug(f"{type((await tab.select('.shopee-product-comment-list')).parent.style) = }")
            try:
                if 'opacity: 1;' in (await tab.select('.shopee-product-comment-list')).parent.style:
                    break
            except Exception as e:
                log.debug(f'exception: {e}')
                error = True
                break
        if error:
            break
        # time.sleep(.5)
    return {
        'title':  title,
        'link': link,
        'sold': no_sold,
        'comments': cmt_list
    }

    
def skip_product(title) -> bool:
    file_path = os.path.join('products', f'{get_file_name(title)}')
    return os.path.exists(file_path)
    
def parse_string_arr(inp):
    return [i['value'] for i in inp if 'value' in i]

def unpack_to_dict(data):
    """
    Converts the nested data structure to a list of dictionaries.
    
    Args:
        data: List of objects with nested 'type' and 'value' structure
        
    Returns:
        List of dictionaries with simple key-value pairs
    """
    result = []
    
    for item in data:
        if item['type'] == 'object':
            obj_dict = {}
            for key, value_info in item['value']:
                obj_dict[key] = value_info['value']
            result.append(obj_dict)
    
    return result

def get_file_name(s):
    # Remove invalid filename characters and replace with underscores
    clean_title = re.sub(r'[<>:"/\\|?*]', '_', s)
    # Remove extra whitespace and replace with underscores
    clean_title = re.sub(r'\s+', '_', clean_title.strip())
    return  f"{clean_title}.json"

def write_object_to_json(obj, output_dir="products"):
    """
    Write a list of objects to separate JSON files using 'title' as filename.
    
    Args:
        objects_list (list): List of dictionaries containing objects with 'title' field
        output_dir (str): Directory to save the JSON files (default: "output")
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    if 'title' not in obj:
        log.warning(f"Object missing 'title' field, skipping: {obj}")
        return
    
    
    filename = get_file_name(obj['title'])
    filepath = os.path.join(output_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)
        log.debug(f"Successfully wrote: {filepath}")
    except Exception as e:
        log.debug(f"Error writing {filepath}: {e}")
        
    # ⚙️ Cấu hình kết nối MySQL
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="180605",  # ⚠️ thay mật khẩu bạn đã đặt
        database="shopee_data"
    )
    cursor = conn.cursor()
        
    # 1️⃣ Thêm sản phẩm
    cursor.execute("""
        INSERT INTO products (title, link, sold)
        VALUES (%s, %s, %s)
    """, (
        obj.get("title"),
        obj.get("link"),
        f"Đã bán {len(obj['comments'])} sản phẩm"
    ))
    product_id = cursor.lastrowid

    # 2️⃣ Thêm review
    for c in obj.get("comments", []):
        cursor.execute("""
            INSERT INTO reviews (product_id, username, metadata, rating, comment)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            product_id,
            c.get("username"),
            c.get("metadata"),
            c.get("rating"),
            c.get("comment")
        ))

    conn.commit()

log_path = os.path.join('log','main.log')
Path(os.path.split(log_path)[0]).mkdir(parents=True, exist_ok=True)
log: logging.Logger = logging.getLogger('Main')
log.setLevel(logging.DEBUG)
stream_log_handler = logging.StreamHandler()
stream_log_handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
file_log_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
log_format = logging.Formatter(
    '[%(asctime)s][%(levelname)s][%(threadName)s][%(funcName)s]: %(message)s', datefmt='%d-%m-%Y][%H:%M:%S')
stream_log_handler.setFormatter(log_format)
file_log_handler.setFormatter(log_format)
log.addHandler(stream_log_handler)
log.addHandler(file_log_handler)
if __name__ == '__main__':
    # since asyncio.run never worked (for me)
    log.info('Starting main...')
    uc.loop().run_until_complete(main())
