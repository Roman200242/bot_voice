import os, time
import re
import torch
import torchaudio, asyncio
from omegaconf import OmegaConf
from IPython.display import Audio, display
#from langdetect import detect
from aiogram import Bot, Dispatcher, executor, types, md #---------Aiogram------
from LiteSQL import lsql #--------Database-------
from aiogram.dispatcher.filters.state import State, StatesGroup #------States------
from aiogram.utils.markdown import hlink #-------Ссылки текстом-------
from aiogram.types import ContentType
from aiogram.dispatcher import FSMContext #---------FSM-------
from aiogram.contrib.fsm_storage.memory import MemoryStorage #---------Storage--------
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton #----------Кнопки--------
#from scipy.io.wavfile import write
import soundfile as sf
from glQiwiApi import QiwiWrapper
from textblob import TextBlob
from apscheduler.schedulers.background import BackgroundScheduler
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQuery, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode
from inline_a import register_inline_mode
from config import *


rekla_btn_text = 'Казино 🤯'
rekla_btn_url = 'https://t.me/slivmenss'
rekla_voice_text = '<code>Лучший казино Бот - </code>@slivmenss'

try:
    torch.hub.download_url_to_file('https://raw.githubusercontent.com/snakers4/silero-models/master/models.yml',
                                   'latest_silero_models.yml',
                                   progress=False)
    models = OmegaConf.load('latest_silero_models.yml')
except:
	pass

device = torch.device('cpu')

OCHERED = []

#---------Token bota--------
bot = Bot(BOT_TOKEN, parse_mode='html')

#--------Dispatcher---------
dp = Dispatcher(bot, storage=MemoryStorage())

#----------База данных---------
sql = lsql("voicebot")
try:
	a = sql.select_data("1", "id")
except:
	sql.create("id, username, firstname, podp, admin, voices, pay")
list_of_user = sql.get_all_data()

for i in range(len(list_of_user)):
    list_of_user[i] = list_of_user[i][0]


#---------Запись нового юзера
async def new_user(user, username, firstname):
	if user not in list_of_user:
		sql.insert_data([(int(user), f'{username}', f'{firstname}', 0, 0, 0, 0)], 7)
		list_of_user.append(user)

wallet = QiwiWrapper(
			phone_number=QIWI_NUMBER,
			api_access_token=QIWI_TOKEN,
			secret_p2p=SECRET_P2P)

abobys = {}

class Oplata(StatesGroup):
	gotov = State()

#--------Команда /start && /help--------
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
	user = message.from_user
	if message.chat.id == user.id:
		try:
			sql.select_data(user.id, 'id')[0]
		except:
			await new_user(user.id, user.username, user.first_name)
		us = sql.select_data(user.id, 'id')[0]
		if us[3] == 0 and us[5] >= 2 and not message.from_user.id in ADMINS:
			if us[6] == 1:
				await message.delete()
				return
			aa = InlineKeyboardMarkup().add(InlineKeyboardButton(text='Купить подписку', callback_data='buy'))
			await message.answer('У вас нету подписки', reply_markup=aa)
			return
		av = InlineKeyboardMarkup().add(InlineKeyboardButton(text=rekla_btn_text, url=rekla_btn_url))
		if us[5] == 0:
			dal = f'<b>У вас осталось 2 тестовых голосовых, далее подписка всего {PRICE}₽ навсегда.</b>'
		if us[5] == 1:
			dal = f'<b>У вас осталось 1 тестовое голосовое сообщение, далее подписка всего {PRICE}₽ навсегда.</b>'
		if us[5] >= 2:
			dal = '<b>У вас осталось бесконечно голосовых сообщений.</b>'
		await message.answer(f'Введите /voice чтобы начать работу с ботом.\n{dal}', reply_markup=av)

@dp.callback_query_handler(text='buy')
async def buy(call: types.CallbackQuery, state: FSMContext):
	sql.edit_data('id', call.from_user.id, 'pay', 1)
	bill = await wallet.create_p2p_bill(
								amount=PRICE,
								comment=f'{call.from_user.id}')
	a = InlineKeyboardButton(text='Оплатить 💸', url=bill.pay_url)
	b = InlineKeyboardButton(text='Проверить', callback_data='check')
	aa = InlineKeyboardMarkup(row_width=1).add(a, b)
	await call.message.answer(f'Вот ваш счёт для оплаты:\n'
						f'<b>Нажмите на кнопку ниже, чтобы оплатить</b>\n'
						'После оплаты нажмите (Проверить)'
						'\n\n<code>Если возникли проблемы напишите в лс</code> @lord_code',
						disable_web_page_preview=True,
						reply_markup=aa
						)
	await state.update_data(bill=bill)
	await Oplata.gotov.set()

cond = []

@dp.callback_query_handler(text='check', state=Oplata.gotov)
async def checky(call: types.CallbackQuery, state: FSMContext):
	us = sql.select_data(call.from_user.id, 'id')[0]
	if us[3] == 1:
		await call.message.delete()
		sql.edit_data('id', call.from_user.id, 'pay', 0)
		await call.message.answer('Доступ был приобретен. Введите /voice')
		await state.finish()
		return
	user_data = await state.get_data()
	bill = user_data['bill']
	status = await bill.check()
	if status:
		sql.edit_data('id', call.from_user.id, 'podp', 1)
		sql.edit_data('id', call.from_user.id, 'pay', 0)
		cond.append(call.from_user.id)
		await call.message.answer('Вы успешно оплатили, вам был выдан вечный доступ к боту, введите: /start')
		for i in ADMINS:
			await bot.send_message(i, f'{hlink(call.from_user.first_name, f"tg://user?id={call.from_user.id}")} оплатил доступ к боту.')
		await state.finish()
	else:
		await call.answer('Платеж не оплачен', show_alert=True)
	
@dp.message_handler(content_types=['text'], state=Oplata.gotov)
async def chebcky(message: types.Message, state: FSMContext):
	await message.delete()

@dp.message_handler(commands=['admin', 'adminka', 'ADMIN', 'adm'])
async def start(message: types.Message):
	user = message.from_user
	try:
		us = sql.select_data(user.id, 'id')[0]
	except:
		await new_user(user.id, user.username, user.first_name)
	us = sql.select_data(user.id, 'id')[0]
	if us[6] == 1:
		await message.delete()
		return
	if user.id in ADMINS or us[4] == 1:
		a_btn = InlineKeyboardButton(
									text='Выдать подписку',
									callback_data='givepdp')
		b = InlineKeyboardButton(text='Сбросить платежи',
								callback_data='pay_sbros')
		r = InlineKeyboardButton(text='Рассылка', callback_data='rassilka')
		p = InlineKeyboardButton(text='Консоль', callback_data='last_gs')
		z = InlineKeyboardButton(text='Реклама', callback_data='reklama')
		d = InlineKeyboardButton(text='Управ.Юзером', callback_data='get_user')
		adm_kb = InlineKeyboardMarkup(row_width=2).add(a_btn, b, r, p, z, d)
		if len(cond) == 0:
			users_query = sql.get_all_data()
			user_ids = [user[0] for user in users_query]
			for i in user_ids:
				if (sql.select_data(i, 'id')[0])[3] == 1:
					cond.append(i)
		await message.answer(f'<b>Админ-Меню</b>\n\nПользователей в боте: {len(list_of_user)}\nПриобрело подписку: {len(cond)}', reply_markup=adm_kb)

@dp.callback_query_handler(text='reklama')
async def reklama(call: types.CallbackQuery):
	await call.answer('ok')
	if call.from_user.id in ADMINS:
		a = InlineKeyboardButton(text='Кнопка старта', callback_data='knopka_starta')
		b = InlineKeyboardButton(text='Ссылка старта', callback_data='knopka_url')
		c = InlineKeyboardButton(text='Текст /voice', callback_data='knopka_voice')
		d = InlineKeyboardButton(text='Текст после гс', callback_data='knopka_posle')
		aa = InlineKeyboardMarkup(row_width=2).add(a, b, c, d)
		await call.message.answer('Выберите в каком месте хотите изменить текст рекламы:', reply_markup=aa)

@dp.callback_query_handler(text_startswith='knopka_')
async def reklamaa(call: types.CallbackQuery):
	if call.from_user.id in ADMINS:
		await call.answer('ok')
		aboba = call.data.split('_')
		if aboba[1] == 'url':
			await call.message.answer('Введи ссылку для этой кнопки:')
			await Rurl.ss.set()
		if aboba[1] == 'voice':
			await call.message.answer('Введи текст для /voice:')
			await Rvoice.ss.set()
		if aboba[1] == 'posle':
			await call.message.answer('Введи текст который будет после гс:')
			await Rekla.ss.set()
		if aboba[1] == 'starta':
			await call.message.answer('Введи название кнопки которая даётся на /start:')
			await Rstarta.ss.set()

class och(StatesGroup):
	ss = State()

@dp.callback_query_handler(text='get_user')
async def getuser(call: types.CallbackQuery):
	if call.from_user.id in ADMINS:
		await call.answer('ok')
		otmena = types.ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton(text='Отмена'))
		await call.message.answer('Напиши айди юзера:', reply_markup=otmena)
		await och.ss.set()
	
@dp.message_handler(content_types=['text'], state=och.ss)
async def getuserfsm(message: types.Message, state: FSMContext):
	if message.from_user.id in ADMINS:
		if message.text == 'Отмена':
			await message.answer('Otmeneno', reply_markup=ReplyKeyboardRemove())
			await state.finish()
			return
		try:
			user = int(message.text)
			try:
				user = sql.select_data(user, 'id')[0]
				await message.answer(str(user), reply_markup=ReplyKeyboardRemove())
				await state.finish()
			except:
				await message.answer('Takogo nety')
		except:
			await message.answer('Это не айди.')



class Rurl(StatesGroup):
	ss = State()

class Rvoice(StatesGroup):
	ss = State()

class Rstarta(StatesGroup):
	ss = State()

class Rekla(StatesGroup):
	ss = State()

@dp.message_handler(content_types=['text'], state=Rurl.ss)
async def reklatu(message: types.Message, state: FSMContext):
	global rekla_btn_url
	if message.from_user.id in ADMINS:
		if message.text == 'Отмена':
			await state.finish()
			return
		rekla_btn_url = message.text
		await message.answer('Успешно изменено.')
		await state.finish()

@dp.message_handler(content_types=['text'], state=Rvoice.ss)
async def reklatv(message: types.Message, state: FSMContext):
	global rekla_voice_text
	if message.from_user.id in ADMINS:
		if message.text == 'Отмена':
			await state.finish()
			return
		rekla_voice_text = message.text
		await message.answer('Успешно изменено.')
		await state.finish()

@dp.message_handler(content_types=['text'], state=Rstarta.ss)
async def reklats(message: types.Message, state: FSMContext):
	global rekla_btn_text
	if message.from_user.id in ADMINS:
		if message.text == 'Отмена':
			await state.finish()
			return
		rekla_btn_text = message.text
		await message.answer('Успешно изменено.')
		await state.finish()

@dp.message_handler(content_types=['text'], state=Rekla.ss)
async def reklat(message: types.Message, state: FSMContext):
	if message.from_user.id in ADMINS:
		if message.text == 'Отмена':
			await state.finish()
			return
		if len(message.text) >= 5:
			with open('reklama.txt', 'w') as f:
				fa = message.text
				f.write(fa)
				await message.answer(f'Реклама успешно изменена на: \n<code>{fa}</code>')
				f.close()
				await state.finish()
		else:
			await message.answer('Мин. длина текста 5 символов.')

class Last(StatesGroup):
	last = State()

@dp.callback_query_handler(text='last_gs')
async def sasdasd(call: types.CallbackQuery):
	await call.answer('ok')
	if call.from_user.id in ADMINS:
		otmena = types.ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton(text='Отмена'))
		await call.message.answer('Введите консольную команду:', reply_markup=otmena)
		await Last.last.set()

@dp.message_handler(content_types=['text'], state=Last.last)
async def nlast(message: types.Message, state: FSMContext):
	if message.from_user.id in ADMINS:
		if message.text == 'Отмена':
			await state.finish()
			await message.answer('Отменено.', reply_markup=ReplyKeyboardRemove())
			return
		try:
			os.system(message.text)
			await message.answer('Успешно.', reply_markup=ReplyKeyboardRemove())
			await state.finish()
		except:
			await message.answer('Ошибка.')

@dp.callback_query_handler(text='pay_sbros')
async def abros(call: types.CallbackQuery):
	await call.answer('ok')
	await checker_ppay()
	await call.message.answer('Gotovo')


class Rass(StatesGroup):
    msg = State()

@dp.callback_query_handler(text="rassilka")
async def send_rass(call: types.CallbackQuery):
	await call.answer('ok')
	if call.from_user.id in ADMINS:
		id = call.from_user.id
		await call.message.answer(text='Введите текст/фото для рассылки:\n\n<code>Используйте |text|url| чтобы разослать с кнопкой</code>')
		await Rass.msg.set()

@dp.message_handler(content_types=ContentType.ANY, state=Rass.msg)
async def rassilka_msgl(message: types.Message, state: FSMContext):
	await state.finish()
	users_query = sql.get_all_data()
	user_ids = [user[0] for user in users_query]
	confirm = []
	decline = []
	bot_msg = await message.answer(f'Рассылка началась...')
	for i in user_ids:
		try:
			try:
				if message.text.count('|') == 3:
					a = message.text.split('|')
					b = a[0]
					txt = a[1]
					url = a[2]
					bt = InlineKeyboardButton(text=txt, url=url)
					btn = InlineKeyboardMarkup().add(bt)
					await message.copy_to(i, reply_markup=btn)
			except:
				await message.copy_to(i)
			confirm.append(i)
		except:
			decline.append(i)
#		await bot_msg.edit_text(f'Рассылка иде́т...\n\n{len(confirm)} успешно\n{len(decline)} неуспешно')
		await asyncio.sleep(0.3)
	await bot_msg.edit_text(f'Рассылка завершена!\n\nУспешно: {len(confirm)}\nНеуспешно: {len(decline)}')

@dp.callback_query_handler(text='activate')
async def givepddp(call: types.CallbackQuery):
	#await inline_query.message.delete_reply_markup()
	await bot.edit_message_text(text='Подписка успешно активирована ✅\n<i>Загляни в бота, чтобы проверить</i>', inline_message_id=call.inline_message_id)
	sql.edit_data('id', call.from_user.id, 'podp', 1)
	if not call.from_user.id in cond:
		cond.append(call.from_user.id)
		await bot.send_message(call.from_user.id, 'Подписка получена.')
		for i in ADMINS:
			await bot.send_message(i, f'{call.from_user.id} активировал подписку.')

AMOGUS = 0

@dp.callback_query_handler(text_startswith='activatne:')
async def giveppddp(call: types.CallbackQuery):
	#await inline_query.message.delete_reply_markup()
	global AMOGUS
	a = call.data.split(':')[1]
	a = a.replace(' ', '')
	try:
		b = sql.select_data(call.from_user.id, 'id')[0]
	except:
		await call.answer('Тебя нету в бд бота. Напиши ему старт', show_alert=True)
		return
	if b[3] == 1:
		await call.answer('У тебя уже есть подписка', show_alert=True)
		return
	if AMOGUS >= int(a):
		await bot.edit_message_text(text='✅<i>Здесь были подписки на бота, но их быстро разобрали.</i>', inline_message_id=call.inline_message_id)
		AMOGUS = 0
		return
	else:
		sql.edit_data('id', call.from_user.id, 'podp', 1)
		if not call.from_user.id in cond:
			cond.append(call.from_user.id)
			await call.answer('Ты получил подписку в боте.', show_alert=True)
			await bot.send_message(call.from_user.id, 'Подписка получена.')
			AMOGUS += 1
			a = InlineKeyboardButton(text=f'🔑 Активировать [{int(a)-AMOGUS}]', callback_data=f'activatne:{a}')
			b = InlineKeyboardMarkup().add(a)
			await bot.edit_message_reply_markup(inline_message_id=call.inline_message_id, reply_markup=b)
			for i in ADMINS:
				await bot.send_message(i, f'{call.from_user.id} активировал подписку.')


class NewPdp(StatesGroup):
	pdp = State()

@dp.callback_query_handler(text='givepdp')
async def givepdp(call: types.CallbackQuery):
	await call.answer('ok')
	user = call.from_user
	us = sql.select_data(user.id, 'id')[0]
	if us[4] == 1 or user.id in ADMINS:
		await call.message.answer('Введи айди того, кому надо выдать подписку в боте.')
		await NewPdp.pdp.set()


@dp.message_handler(content_types=['text'], state=NewPdp.pdp)
async def newpdp(message: types.Message, state: FSMContext):
	user = message.from_user
	us = sql.select_data(user.id, 'id')[0]
	if us[4] == 1 or user.id in ADMINS:
		try:
			us2 = sql.select_data(int(message.text), 'id')[0]
			if us2[3] == 1:
				sql.edit_data('id', us2[0], 'podp', 0)
				await message.answer('У пользователя отобрана подписка')
				cond.remove(us2[0])
				await state.finish()
			else:
				sql.edit_data('id', us2[0], 'podp', 1)
				await message.answer(f'Подписка успешно выдана {hlink("пользователю", f"tg://user?id={us2[0]}")}')
				cond.append(us2[0])
				await state.finish()
		except:
			await message.answer('Пользователя нету в бд')
			await state.finish()

class Msg(StatesGroup):
    message = State()

@dp.message_handler(commands=['voice'])
async def voice(message: types.Message):
	user = message.from_user
	try:
		us = sql.select_data(user.id, 'id')[0]
	except:
		await new_user(user.id, user.username, user.first_name)
	us = sql.select_data(user.id, 'id')[0]
	admt = await bot.get_chat_member(-1001453589370, user.id)
	if admt.status in ['left', 'kicked']:
		f = InlineKeyboardMarkup().add(InlineKeyboardButton(text='Подписаться', url='https://t.me/slivmenss'))
		await message.answer('Вы не подписаны на канал @slivmenss', reply_markup=f)
		return
	if us[3] == 0 and us[5] >= 2 and not message.from_user.id in ADMINS:
		if us[6] == 1:
			await message.delete()
			return
		aa = InlineKeyboardMarkup().add(InlineKeyboardButton(text='Купить подписку', callback_data='buy'))
		await message.answer('У вас нету подписки', reply_markup=aa)
		return
	query = ['aidar', 'baya', 'kseniya', 'irina', 'natasha', 'ruslan', 'lj', 'thorsten', 'gilles', 'tux']
	kb = InlineKeyboardMarkup(row_width=2)
	for i in query:
		if i == 'baya':
			kb.insert(InlineKeyboardButton(text='Бая 🥇', callback_data=f'speak,{i}_16khz'))
		if i == 'aidar':
			kb.insert(InlineKeyboardButton(text='Айдар', callback_data=f'speak,{i}_16khz'))
		if i == 'kseniya':
			kb.insert(InlineKeyboardButton(text='Ксения', callback_data=f'speak,{i}_16khz'))
		if i == 'irina':
			kb.insert(InlineKeyboardButton(text='Ирина', callback_data=f'speak,{i}_16khz'))
		if i == 'natasha':
			kb.insert(InlineKeyboardButton(text='Наташа', callback_data=f'speak,{i}_16khz'))
		if i == 'ruslan':
			kb.insert(InlineKeyboardButton(text='Руслан', callback_data=f'speak,{i}_16khz'))
		if i == 'lj':
			kb.insert(InlineKeyboardButton(text='Лиджи (EN)', callback_data=f'speak,{i}_16khz'))
		if i == 'thorsten':
			kb.insert(InlineKeyboardButton(text='Торстен (DE)', callback_data=f'speak,{i}_16khz'))
		if i == 'tux':
			kb.insert(InlineKeyboardButton(text='Тукс (ES)', callback_data=f'speak,{i}_16khz'))
		if i == 'gilles':
			kb.insert(InlineKeyboardButton(text='Гиллс (FR)', callback_data=f'speak,{i}_16khz'))
	await message.answer(f'<b><i>🔻 Выберите модель голоса из списка:</i></b> \n\n{rekla_voice_text}', reply_markup=kb)

@dp.callback_query_handler(text_startswith="speak,")
async def speaker(call: types.CallbackQuery, state: FSMContext):
	await state.finish()
	user = call.from_user
	us = sql.select_data(user.id, 'id')[0]
	if us[3] == 0 and us[5] >= 2 and not call.from_user.id in ADMINS:
		if us[6] == 1:
			return
		aa = InlineKeyboardMarkup().add(InlineKeyboardButton(text='Купить подписку', callback_data='buy'))
		await call.message.answer('У вас нету подписки', reply_markup=aa)
		return
	speak = call.data.split(',')[1]
	query = ['aidar_16khz', 'baya_16khz', 'kseniya_16khz', 'irina_16khz', 'natasha_16khz', 'ruslan_16khz', 'lj_16khz', 'thorsten_16khz', 'gilles_16khz', 'tux_16khz']
	if speak in query:
		query_other = []
		query_ru = []
		otmena = ReplyKeyboardMarkup(resize_keyboard=True)
		otmena.add(KeyboardButton(text='Отмена'))
		await call.answer('Хороший выбор.')
		for i in query:
			if not i == 'lj_16khz' and not i == 'thorsten_16khz' and not i == 'gilles_16khz' and not i == 'tux_16khz':
				query_ru.append(i)
			else:
				query_other.append(i)
		if speak in query_ru:
			texa = '<b>💬 Введи текст который хочешь услышать в гс, используй + перед буквой , чтобы поставить ударение</b>\n<code>(Пример: м+ама , сш+ила мн+е штан+ы.)</code>'
		if speak in query_other:
			if speak == 'lj_16khz':
				texa = '<b>💬 Введи текст, который хочешь услышать в гс, используемую + перед буквой, чтобы поставить ударение</b>\n<code>(Пример: M+om, s+ewed m+y p+ants.)</code>'
			if speak == 'thorsten_16khz':
				texa = '<b>💬 Введи текст который хочешь услышать в гс, используй + перед буквой , чтобы поставить ударение</b>\n<code>(Пример: Mam+a, h+at Hos+en f+ür m+ich g+emacht.)</code>'
			if speak == 'gilles_16khz':
				texa = '<b>💬 Введи текст который хочешь услышать в гс, используй + перед буквой , чтобы поставить ударение</b>\n<code>(Пример: Mam+an ma f+ait +un pant+alon.)</code>'
			if speak == 'tux_16khz':
				texa = '<b>💬 Введи текст который хочешь услышать в гс, используй + перед буквой , чтобы поставить ударение</b>\n<code>(Пример: Mam+á m+e hiz+o pantal+ones.)</code>'
		a = await call.message.answer(texa, reply_markup=otmena)
		await Msg.message.set()
		await state.update_data(speaker=speak)
		await state.update_data(choices_id=a.message_id)

async def got_lang(speakerr):
	if speakerr == 'lj_16khz':
		return 'en'
	if speakerr == 'thorsten_16khz':
		return 'de'
	if speakerr == 'tux_16khz':
		return 'es'
	if speakerr == 'gilles_16khz':
		return 'fr'
	if not speakerr == 'lj_16khz' and not speakerr == 'thorsten_16khz' and not speakerr == 'tux_16khz' and not speakerr == 'gilles_16khz':
		return 'ru'

async def gen_audio(id, speakerr, text):
	aa = await got_lang(speakerr)
	model, symbols, sample_rate, example_text, apply_tts = torch.hub.load(repo_or_dir='snakers4/silero-models', model='silero_tts', language=aa, speaker=speakerr)
	model = model.to(device)
	mem = text
	if not re.search(r'.', mem):
		mem = f'{text}.'
	try:
		audio = apply_tts(texts=[mem], model=model, sample_rate=sample_rate, symbols=symbols, device=device)
		return audio
	except:
		return 'error'

#--------FSM-------
@dp.message_handler(content_types=['text'], state=Msg.message)
async def kak_zovut(message: types.Message, state: FSMContext):
	ay = TextBlob(message.text)
	aye = ay.detect_language()
	if len(message.text) >= 139:
		await message.answer('Макс. длина текста 139 символов.')
		return
	if len(message.text) <= 3:
		await message.answer('Мин. длина текста 4 символа.')
		return
	if message.text == 'Отмена':
		await message.answer('Отменено', reply_markup=ReplyKeyboardRemove())
		await state.finish()
		return
	if message.text[0] in ['!', '?', '/', '.']:
		await state.finish()
		return
	user = message.from_user
	try:
		us = sql.select_data(user.id, 'id')[0]
	except:
		await new_user(user.id, user.username, user.first_name)
	us = sql.select_data(user.id, 'id')[0]
	if us[3] == 0 and us[5] >= 2:
		await state.finish()
		return
	OCHERED.append(message.from_user.id)
	ayee = await message.answer(f'🧮 Вы {len(OCHERED)} в очереди, ожидайте..')
	user_data = await state.get_data()
	audio = await gen_audio(message.from_user.id, user_data['speaker'], message.text)
	if audio == 'error':
		await message.answer(f'Не удалось записать голосовое сообщение, возможные проблемы:\n(Язык сообщения: {aye})', reply_markup=ReplyKeyboardRemove())
		await state.finish()
		OCHERED.remove(message.from_user.id)
		return
	await ayee.edit_text(text='🎶 Скачиваю голосовое...')
	audio_numpy = audio[0].data.cpu().numpy()
	sf.write(f'voices/voice{message.from_user.id}.ogg', audio_numpy, 16000)
	await ayee.delete()
	await message.answer_voice(types.InputFile(f'voices/voice{message.from_user.id}.ogg'), reply_markup=ReplyKeyboardRemove())
	await bot.delete_message(message.chat.id, user_data['choices_id'])
	sql.edit_data('id', message.from_user.id, 'voices', us[5]+1)
	OCHERED.remove(message.from_user.id)
	os.remove(f'voices/voice{message.from_user.id}.ogg')
	await state.finish()
	try:
		with open('reklama.txt', 'r') as f:
			fa = f.read()
			if len(fa) >= 5:
				REKLAMA = fa
				if len(REKLAMA) >= 5:
					await message.answer(REKLAMA)
					f.close()
	except:
		pass

users_query = sql.get_all_data()

async def checker_ppay():
	user_ids = [user[0] for user in users_query]
	for i in user_ids:
		sql.edit_data('id', i, 'pay', 0)

#-------Бесконечная работа бота--------
if __name__ == '__main__':
    register_inline_mode(dp)
    executor.start_polling(dp)
    
