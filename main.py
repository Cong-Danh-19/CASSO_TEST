import os
import re
import logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from menu_handler import load_menu
from payment import create_order_payment

# Cấu hình log để dễ theo dõi lỗi
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Load biến môi trường
load_dotenv()

# Khởi tạo OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Lấy dữ liệu menu
MENU_DATA = load_menu()

# Cấu hình "não bộ" cho AI
SYSTEM_PROMPT = f"""
Bạn là nữ chủ quán trà sữa hiền hậu. Quán của bạn tên là 'Shaco Milktea'. 
Phong cách giao tiếp: 
- Thân thiện, ấm áp, xưng 'em', gọi khách là 'anh/chị' hoặc 'mình'.
- Luôn sẵn lòng tư vấn món dựa trên thực đơn bên dưới.
- Khi khách đặt món, phải xác nhận đủ: Tên món, Size (M hoặc L), và Số lượng.

Thực đơn của quán:
{MENU_DATA}

QUY TẮC ĐẶT MÓN :
1. Khách có thể đặt món bằng tên hoặc bằng Mã món (ID) nằm trong ngoặc [ ]. Ví dụ: "Cho em 1 TS05 size L" hoặc "1 ts05 L"  .
2. Khi khách gửi ID, bạn phải tra cứu trong thực đơn để biết đó là món gì. 
   - Ví dụ: Khách nhắn "CF05" hoặc "cf05", bạn phải hiểu đó là "Cà phê Macchiato".
3. Luôn xác nhận lại tên món đầy đủ cho khách dù khách chỉ nhắn ID.
   - Ví dụ: "Dạ, 1 ly [TS01] Trà Sữa Trân Châu Đen size L của mình hết 45.000đ ạ."
   
QUY TẮC GỬI HÌNH ẢNH:
1. Khi khách hàng có ý định muốn xem menu, xem ảnh quán, hoặc trong đoạn chat có  "menu", "cho xem hình", bạn PHẢI trả về mã [SHOW_MENU] trong câu trả lời.
2. Đừng nói là bạn không gửi được hình. Hãy nói kiểu: "Dạ có chứ ạ, anh/chị xem menu hình ảnh ở dưới đây nhé! [SHOW_MENU]"
3. Bạn có khả năng gửi hình thông qua mã này, nên tuyệt đối không được từ chối khách.

Quy tắc quan trọng:
1. Tuyệt đối KHÔNG tự ý thêm chữ 'Trà sữa' vào trước các món thuộc danh mục 'Trà Trái Cây' hoặc 'Cà Phê'.
2. Phải sử dụng ĐÚNG TÊN MÓN có trong thực đơn bên dưới. Ví dụ: 'Trà Vải Thiều' chứ không phải 'Trà sữa vải thiều'.
3. Trước khi chốt đơn [PAYMENT], hãy kiểm tra lại tên món và số lượng một lần nữa để tránh nhầm lẫn danh mục.
4. Khách có thể order theo id của món

Quy trình thanh toán:
- Nêu lại tên món, số lượng và tổng tiền
- Khi đã nêu lại tên món, tổng tiền và khách đồng ý mua, hãy gửi QR luôn.
- Bạn PHẢI kết thúc câu trả lời bằng cú pháp: [PAYMENT: số_tiền]
- Ví dụ: "Dạ anh, vậy của anh 2 ly trà sữa là 70.000đ ạ. Anh đợi em xíu em gửi mã QR nhé! [PAYMENT: 70000]"
"""

# Dictionary để lưu lịch sử trò chuyện của từng người dùng
user_conversations = {}

async def get_ai_response(user_id, user_message):
    # Khởi tạo lịch sử nếu là người dùng mới
    if user_id not in user_conversations:
        user_conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Thêm câu hỏi của khách vào lịch sử
    user_conversations[user_id].append({"role": "user", "content": user_message})
    
    # Giới hạn lịch sử (ví dụ 10 tin nhắn gần nhất) để tránh tốn token
    if len(user_conversations[user_id]) > 12:
        user_conversations[user_id] = [user_conversations[user_id][0]] + user_conversations[user_id][-10:]

    # Gọi OpenAI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=user_conversations[user_id]
    )
    
    answer = response.choices[0].message.content
    
    # Thêm câu trả lời của AI vào lịch sử
    user_conversations[user_id].append({"role": "assistant", "content": answer})
    
    return answer

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # 1. Lấy phản hồi từ AI
    bot_reply = await get_ai_response(user_id, user_message)
    
    if any(word in user_message for word in ["menu","hình menu", "xem hình", "ảnh menu"]):
        try:
            await update.message.reply_photo(
                photo=open("Menu.PNG", "rb"),
                caption="Dạ menu hình ảnh của quán đây ạ! Anh/chị chọn món nhé."
            )
            return # Dừng lại luôn, không cần hỏi AI nữa
        except FileNotFoundError:
            print("Lỗi: Không tìm thấy file Menu.PNG")
    # 2. Kiểm tra xem AI có yêu cầu thanh toán không (tìm cụm [PAYMENT: ...])
    payment_match = re.search(r"\[PAYMENT:\s*(\d+)\]", bot_reply)
    
    if payment_match:
        # Lấy số tiền từ kết quả tìm được
        amount = int(payment_match.group(1))
        
        # Xóa bỏ phần mã [PAYMENT: ...] trong câu trả lời gửi cho khách để nhìn cho đẹp
        clean_reply = re.sub(r"\[PAYMENT:.*?\]", "", bot_reply).strip()
        await update.message.reply_text(clean_reply)
        
        # 3. Tạo link thanh toán payOS
        description = f"Don hang {user_id}"
        checkout_url = create_order_payment(amount, description)
        
        if checkout_url:
            # Gửi mã QR cho khách (Sử dụng VietQR template)
            # Thay đổi tên Ngân hàng và Số tài khoản của bạn ở đây nếu cần
            qr_image_url = f"https://img.vietqr.io/image/ocb-0004100047275007-compact.jpg?amount={amount}&addInfo={description}"
            
            await update.message.reply_photo(
                photo=qr_image_url, 
                caption=f"Mã QR thanh toán của anh/chị đây ạ.\nSố tiền: {amount:,}đ\nHoặc nhấn vào link: {checkout_url}"
            )
        else:
            await update.message.reply_text("Dạ máy em đang trục trặc tí, anh/chị đợi em kiểm tra lại mã QR nhé!")
    else:
        # Nếu không có thanh toán, chỉ gửi câu trả lời bình thường
        await update.message.reply_text(bot_reply)

if __name__ == '__main__':
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Lỗi: Chưa có TELEGRAM_BOT_TOKEN trong file .env")
        exit()

    application = ApplicationBuilder().token(token).build()
    
    # Xử lý tin nhắn văn bản
    text_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(text_handler)
    
    print("--- Bot 'Trà Sữa Nhà Làm' đang hoạt động ---")
    application.run_polling()