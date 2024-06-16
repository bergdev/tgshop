import os
import random
import telebot
import webbrowser
from telebot import types
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.exc import OperationalError, IntegrityError


# Считываем токен бота из файла mytoken.txt
with open('./mytoken.txt') as file:
    mytoken = file.read().strip()

# Создаем экземпляр бота, используя токен
bot = telebot.TeleBot(mytoken)

# Настройки базы данных
Base = declarative_base()
engine = create_engine('sqlite:///shop.db')
Session = sessionmaker(bind=engine)
session = Session()

# Модели базы данных
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    username = Column(String, unique=True)
    password = Column(String)
    is_seller = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    sales_count = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    products = relationship('Product', back_populates='seller')

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    price = Column(Float)
    photo = Column(String)  # Путь к фото
    seller_id = Column(Integer, ForeignKey('users.id'))
    seller = relationship('User', back_populates='products')

class Review(Base):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    rating = Column(Integer)
    comment = Column(String)

# Функция для выполнения миграции базы данных
def migrate():
    try:
        with engine.connect() as connection:
            # Проверка на наличие столбцов
            result = connection.execute(text("PRAGMA table_info(users)")).fetchall()
            user_columns = [row[1] for row in result]
            if 'sales_count' not in user_columns:
                connection.execute(text('ALTER TABLE users ADD COLUMN sales_count INTEGER DEFAULT 0'))
            if 'rating' not in user_columns:
                connection.execute(text('ALTER TABLE users ADD COLUMN rating FLOAT DEFAULT 0.0'))
            if 'is_admin' not in user_columns:
                connection.execute(text('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE'))
            
            result = connection.execute(text("PRAGMA table_info(products)")).fetchall()
            product_columns = [row[1] for row in result]
            if 'photo' not in product_columns:
                connection.execute(text('ALTER TABLE products ADD COLUMN photo STRING'))
    except OperationalError as e:
        print(f"Ошибка миграции: {e}")

# Выполняем миграцию базы данных
migrate()

Base.metadata.create_all(engine)

# Список вариантов ответов, если бот не понимает сообщение пользователя
answers = ['Я не понял, что ты хочешь сказать.', 'Извини, я тебя не понимаю.', 'Я не знаю такой команды.', 'Мой разработчик не говорил, что отвечать в такой ситуации... >_<']

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def welcome(message):
    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    if not user:
        user = User(user_id=message.from_user.id, first_name=message.from_user.first_name, last_name=message.from_user.last_name, username=message.from_user.username)
        session.add(user)
        session.commit()
        # Проверка, если это вы (администратор)
        if message.from_user.username == 'exefi1e':
            user.is_admin = True
            session.commit()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = types.KeyboardButton('🛍 Все товары')
    button2 = types.KeyboardButton('🛍 Мои товары')
    button3 = types.KeyboardButton('📄 Справка')
    button4 = types.KeyboardButton('🔑 Вход')
    button5 = types.KeyboardButton('🔑 Регистрация')
    button6 = types.KeyboardButton('👥 Все пользователи')
    button7 = types.KeyboardButton('🔸 Стать продавцом')  # Новая кнопка для становления продавцом
    button8 = types.KeyboardButton('🔍 Поиск товаров')
    markup.row(button1, button2)
    markup.row(button3)
    if not user.username:
        markup.row(button4, button5)
    markup.row(button6, button7)
    markup.row(button8)
    
    # Добавьте кнопки для продавцов
    if user.is_seller or user.is_admin:
        button_add = types.KeyboardButton('🔸 Добавить товар')
        button_delete = types.KeyboardButton('🔸 Удалить товар')
        markup.row(button_add, button_delete)

    admin_tag = ' (админ)' if user.is_admin else ''
    bot.send_message(message.chat.id, f'Привет, {message.from_user.first_name}{admin_tag}!\nЗдесь можно купить/продать виртуальные товары и услуги\nКонтакт моих разработчиков: https://t.me/exefi1e \n', reply_markup=markup)

# Обработка фото
@bot.message_handler(content_types='photo')
def get_photo(message):
    bot.send_message(message.chat.id, 'У меня нет возможности просматривать фото :(')

# Обработка обычных текстовых команд, описанных в кнопках
@bot.message_handler()
def info(message):
    if message.chat.type != 'private':
        return

    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    if not user:
        bot.send_message(message.chat.id, 'Пожалуйста, сначала введите команду /start для начала работы.')
        return
    
    if message.text == '🛍 Все товары':
        all_goods(message)
    elif message.text == '🛍 Мои товары':
        my_goods(message)
    elif message.text == '📄 Справка':
        infoChapter(message)
    elif message.text == '👥 Все пользователи':
        show_users(message)
    elif message.text.startswith('🔹'):
        product_name = message.text[2:].strip()
        product = session.query(Product).filter_by(name=product_name).first()
        if product:
            show_product_info(message, product.id)
        else:
            bot.send_message(message.chat.id, 'Товар не найден.')
    elif message.text == '✏️ Написать разработчику':
        webbrowser.open('https://t.me/exefi1e')
    elif message.text == '↩️ Назад':
        goodsChapter(message)
    elif message.text == '↩️ Назад в меню':
        welcome(message)
    elif message.text == '🔸 Добавить товар' and user.is_seller:
        bot.send_message(message.chat.id, 'Отправьте название товара:')
        bot.register_next_step_handler(message, get_product_name)
    elif message.text == '🔸 Удалить товар' and (user.is_seller or user.is_admin):
        delete_product(message, user)
    elif message.text == '🔸 Стать продавцом':
        make_seller(message)  # Добавьте обработку для становления продавцом
    elif message.text == '🔍 Поиск товаров':
        search_products(message)  # Добавьте обработку для поиска товаров
    else:
        bot.send_message(message.chat.id, random.choice(answers))

# Обработчики для становления продавцом и поиска товаров
def make_seller(message):
    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    if user.is_seller:
        bot.send_message(message.chat.id, 'Вы уже являетесь продавцом.')
    else:
        user.is_seller = True
        session.commit()
        bot.send_message(message.chat.id, 'Теперь вы стали продавцом!')

def search_products(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('↩️ Назад в меню'))
    bot.send_message(message.chat.id, 'Введите название товара для поиска:', reply_markup=markup)
    bot.register_next_step_handler(message, perform_search)

def perform_search(message):
    if message.text == '↩️ Назад в меню':
        welcome(message)
        return

    query = message.text
    products = session.query(Product).filter(Product.name.like(f"%{query}%")).all()
    if products:
        for product in products:
            caption = f"{product.name}\n{product.description}\nЦена: {product.price} руб.\nПродавец: {product.seller.first_name} {product.seller.last_name}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('Купить', callback_data=f'buy_{product.id}'))
            if product.photo:
                try:
                    with open(product.photo, 'rb') as photo:
                        bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=markup)
                except FileNotFoundError:
                    bot.send_message(message.chat.id, f"Фото товара '{product.name}' не найдено.\n{caption}", reply_markup=markup)
            else:
                bot.send_message(message.chat.id, caption, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Товары не найдены.')

# Функции для работы с товарами
def get_product_name(message):
    product_name = message.text
    bot.send_message(message.chat.id, 'Отправьте описание товара:')
    bot.register_next_step_handler(message, get_product_description, product_name)

def get_product_description(message, product_name):
    product_description = message.text
    bot.send_message(message.chat.id, 'Отправьте цену товара:')
    bot.register_next_step_handler(message, get_product_price, product_name, product_description)

def get_product_price(message, product_name, product_description):
    try:
        product_price = float(message.text)
        bot.send_message(message.chat.id, 'Отправьте фото товара:')
        bot.register_next_step_handler(message, get_product_photo, product_name, product_description, product_price)
    except ValueError:
        bot.send_message(message.chat.id, 'Цена должна быть числом. Попробуйте еще раз.')
        bot.register_next_step_handler(message, get_product_price, product_name, product_description)

def get_product_photo(message, product_name, product_description, product_price):
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, 'Пожалуйста, отправьте фото товара.')
        bot.register_next_step_handler(message, get_product_photo, product_name, product_description, product_price)
        return

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    photo_path = f'./photos/{message.photo[-1].file_id}.jpg'
    with open(photo_path, 'wb') as photo_file:
        photo_file.write(downloaded_file)

    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    new_product = Product(name=product_name, description=product_description, price=product_price, photo=photo_path, seller=user)
    session.add(new_product)
    session.commit()

    bot.send_message(message.chat.id, f'Товар "{product_name}" успешно добавлен!')

def delete_product(message, user):
    products = session.query(Product).filter_by(seller=user).all()
    if not products:
        bot.send_message(message.chat.id, 'У вас нет товаров для удаления.')
        return

    markup = types.InlineKeyboardMarkup()
    for product in products:
        markup.add(types.InlineKeyboardButton(product.name, callback_data=f'delete_{product.id}'))
    bot.send_message(message.chat.id, 'Выберите товар для удаления:', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def confirm_delete(call):
    product_id = int(call.data.split('_')[1])
    product = session.query(Product).get(product_id)
    if product:
        photo_path = product.photo
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)  # Удаление фото товара
        session.delete(product)
        session.commit()
        bot.send_message(call.message.chat.id, 'Товар успешно удален.')

# Обработка покупки товара
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_product(call):
    product_id = int(call.data.split('_')[1])
    product = session.query(Product).get(product_id)
    if product:
        buyer = session.query(User).filter_by(user_id=call.from_user.id).first()
        if buyer.user_id == product.seller.user_id:
            bot.send_message(call.message.chat.id, 'Вы не можете купить собственный товар!.')
        else:
            # Отправка сообщения покупателю
            bot.send_message(call.message.chat.id, f"Вы купили товар '{product.name}'. Подождите, продавец свяжется с вами.")
            
            # Отправка сообщения продавцу с ссылкой на покупателя
            if product.seller.username:
                seller_tg_link = f"https://t.me/{product.seller.username}"
                bot.send_message(product.seller.user_id, f"Ваш товар '{product.name}' был куплен. Свяжитесь с покупателем: [ссылка на Telegram покупателя](https://t.me/{buyer.username})", parse_mode="Markdown")
            else:
                bot.send_message(product.seller.user_id, f"Ваш товар '{product.name}' был куплен. Свяжитесь с покупателем: [ссылка на Telegram покупателя](https://t.me/{buyer.username})", parse_mode="Markdown")

# Функция для отображения всех товаров
def all_goods(message):
    products = session.query(Product).all()
    if not products:
        bot.send_message(message.chat.id, 'Товаров пока нет.')
        return

    for product in products:
        caption = f"{product.name}\n{product.description}\nЦена: {product.price} руб.\nПродавец: {product.seller.first_name} {product.seller.last_name}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Купить', callback_data=f'buy_{product.id}'))
        if product.photo:
            try:
                with open(product.photo, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=markup)
            except FileNotFoundError:
                bot.send_message(message.chat.id, f"Фото товара '{product.name}' не найдено.\n{caption}", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, caption, reply_markup=markup)

# Функция для отображения товаров конкретного пользователя
def my_goods(message):
    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    products = session.query(Product).filter_by(seller=user).all()
    if not products:
        bot.send_message(message.chat.id, 'У вас пока нет товаров.')
        return

    for product in products:
        caption = f"{product.name}\n{product.description}\nЦена: {product.price} руб.\nПродавец: {product.seller.first_name} {product.seller.last_name}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Купить', callback_data=f'buy_{product.id}'))
        if product.photo:
            try:
                with open(product.photo, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=markup)
            except FileNotFoundError:
                bot.send_message(message.chat.id, f"Фото товара '{product.name}' не найдено.\n{caption}", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, caption, reply_markup=markup)

# Функция для отображения информации о товаре
def show_product_info(message, product_id):
    product = session.query(Product).get(product_id)
    if product:
        caption = f"{product.name}\n{product.description}\nЦена: {product.price} руб.\nПродавец: {product.seller.first_name} {product.seller.last_name}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Купить', callback_data=f'buy_{product.id}'))
        if product.photo:
            try:
                with open(product.photo, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=markup)
            except FileNotFoundError:
                bot.send_message(message.chat.id, f"Фото товара '{product.name}' не найдено.\n{caption}", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, caption, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Товар не найден.')

# Функция для отображения всех пользователей
def show_users(message):
    users = session.query(User).all()
    if not users:
        bot.send_message(message.chat.id, 'Пользователей пока нет.')
        return

    for user in users:
        user_info = f"{user.first_name} {user.last_name} (@{user.username})"
        if user.is_seller:
            user_info += " - Продавец"
        if user.is_admin:
            user_info += " - Админ"
        bot.send_message(message.chat.id, user_info)

# Функция для отображения справочной информации
def infoChapter(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('↩️ Назад в меню'))
    bot.send_message(message.chat.id, 'Этот бот предназначен для покупки и продажи виртуальных товаров и услуг.', reply_markup=markup)

# Функция для отображения всех товаров
def goodsChapter(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('🛍 Все товары'))
    markup.add(types.KeyboardButton('🛍 Мои товары'))
    markup.add(types.KeyboardButton('↩️ Назад в меню'))
    bot.send_message(message.chat.id, 'Выберите категорию товаров:', reply_markup=markup)

# Запуск бота
bot.polling(none_stop=True)