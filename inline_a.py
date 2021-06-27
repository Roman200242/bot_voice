from aiogram import types, Dispatcher
from aiogram.utils.markdown import hcode
from aiogram import types
import hashlib
from aiogram.types import InlineQuery, \
	InlineQueryResultArticle, \
	InputTextMessageContent, ParseMode, \
	InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMINS



async def give_subscription(inline_query: types.InlineQuery):
    text = f'<b>Чтобы активировать подписку нажми на кнопку ниже:</b>'
    print(inline_query.query)

    result_id: str = hashlib.md5(text.encode()).hexdigest()
    input_content = InputTextMessageContent(text, parse_mode=ParseMode.HTML)
    item = InlineQueryResultArticle(
            id=result_id,
            title=f'Выдать подписку',
            input_message_content=input_content,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton('🔑  Активировать',
                                      callback_data=f'activate')]])
        )

    await inline_query.answer(results=[item], cache_time=1)

async def checks(inline_query: types.InlineQuery):
    text = f'<b>Подарок от Админов\nЧтобы активировать подписку нажми на кнопку ниже</b>'

    result_id: str = hashlib.md5(text.encode()).hexdigest()
    input_content = InputTextMessageContent(text, parse_mode=ParseMode.HTML)
    item = InlineQueryResultArticle(
            id=result_id,
            title=f'Тоже самoе в канал',
            input_message_content=input_content,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(f'🔑 Активировать [{inline_query.query}]',
                                      callback_data=f'activatne:{inline_query.query}')]])
        )

    await inline_query.answer(results=[item], cache_time=1)

def register_inline_mode(dp: Dispatcher):
    dp.register_inline_handler(give_subscription, lambda query: query.query is '', state='*', user_id=ADMINS)
    dp.register_inline_handler(checks, lambda query: not query.query is '', state='*', user_id=ADMINS)