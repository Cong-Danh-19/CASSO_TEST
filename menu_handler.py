import pandas as pd

def load_menu():
    try:
        # Đọc file CSV
        df = pd.read_csv('Menu.csv')
        
        # Chỉ lấy các món còn hàng (available == True)
        available_menu = df[df['available'] == True]
        
        menu_content = "DANH SÁCH THỰC ĐƠN CỦA QUÁN:\n"
        for _, row in available_menu.iterrows():
            menu_content += f"- {row['name']} ({row['category']}): Size M: {row['price_m']:,}đ, Size L: {row['price_l']:,}đ. Mô tả: {row['description']}\n"
        
        return menu_content
    except Exception as e:
        return f"Lỗi khi đọc menu: {e}"

# Test nhanh xem đã đọc được chưa
if __name__ == "__main__":
    print(load_menu())