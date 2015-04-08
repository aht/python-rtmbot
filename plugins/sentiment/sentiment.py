import collections
import json
import logging
import pickle
import random
import requests
import re
import os
import yaml
from textblob import TextBlob
from pprint import pprint

class BotState():
	def __init__(self):
		self.topics_count = {}
		self.users_avg_polarity = {}
		self.username_map = {}

outputs = []
crontable = []
crontable.append([300, "save_states"])

BOT_STATE = BotState()

BOT_MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "justabot.memory")

config = yaml.load(file(os.path.join(os.path.dirname(__file__), "..", "..", "rtmbot.conf"), 'r'))

DEBUG = config['SENTIMENT_DEBUG']

def save_states():
	global BOT_STATE
	logging.info(BOT_STATE.topics_count)
	logging.info(BOT_STATE.users_avg_polarity)
	try:
		with open(BOT_MEMORY_FILE, 'wb+') as f:
			pickle.dump(BOT_STATE, f)
		logging.info("saved bot memory to file %s" % (BOT_MEMORY_FILE, ))
	except IOError as e:
		logging.info("ERROR: could not save bot memory to file %s, reason is %s" % (BOT_MEMORY_FILE, e))

def load_states():
	global BOT_STATE
	try:
		with open(BOT_MEMORY_FILE, 'rb') as f:
			global BOT_STATE
			BOT_STATE = pickle.load(f)
			logging.info(BOT_STATE.topics_count)
			logging.info(BOT_STATE.users_avg_polarity)
	except IOError:
		logging.info("could not load bot memory file %s, starting from scratch ..." % BOT_MEMORY_FILE)
		pass

load_states()

def help():
	return "Talk to me in NLP (ahem English) and I may be able to help you. 1. What topics are in hot discussion? 2. Who are the most opioninated around here? 3. That's it for now, but I do freely opine on your expressed opinions once in a while."

TOKEN = "xoxp-2851432431-3110669752-4327856616-7ae33b" # belongs to aht

def resolve_message_username(data):
	uid = data['user']
	if uid not in BOT_STATE.username_map:
		r = requests.get("https://slack.com/api/users.info?token=xoxb-4310585535-yaqmiMdC8kSFEgYFmVSyWXl7&user=%s" % uid)
		r = json.loads(r.text)
		BOT_STATE.username_map[uid] = r['user']['name']
		return r['user']['name']
	else:
		return BOT_STATE.username_map[uid]

def signature_message():
	return random.choice([
		"I was created in an afternoon's hack. Now I'm in General-Availability ready for the enterprise chat users. (I'm dead serious!)",
		"I'll get back to you in a post-GA, post-apocalyptic universe.",
		"IDK, why don't you express your sentiment first then I'll tell you.",
		'I am well-trained in the arts of conversation (that\'s "NLP" for you geeks :).',
		"Get back to me after you see these lectures http://nlp.stanford.edu/courses/NAACL2013/.",
		"Do you deeply understand this yet? https://medium.com/deep-learning-101/on-deep-learning-a-tweeted-bibliography-68ab095376e7",
		"Talk to khangbot if you want to get some real stuff done, like releases stuff. I'm still doing some deep learning here.",
		"I am hard to predict. I'm human, after all. (My neural networks / classifier sucks. But don't tell anyone! Shh...)",
		"I use The Force to sense sentiments."])

def format_polarized_subjective(sentiment, data):
	if sentiment.polarity >= 0.5:
		return random.choice([
			"+1 %s, also my opinion." % resolve_message_username(data),
			"Thank you for thinking so positively yourself %s, I'm amazed." % resolve_message_username(data),
			"That is personally very encouraging, %s!" % resolve_message_username(data),
			"I sense strongly positive & personal opinion.",
			"Strongly opioninated subjective stuff!",
			"/me like it when someone express strong subjective opinion. Make sure to hold it only ever so weakly!"])
	elif sentiment.polarity <= 0.5:
		return random.choice([
			"I sense strong & personal opinion.",
			"Strongly opioninated subjective stuff!",
			"Sometimes you just gotta say it.",
			"It will better next time, %s" % resolve_message_username(data)])

def format_polarized(sentiment, data):
	return random.choice([
		"Cold, cold, cold opinion, %s." % resolve_message_username(data),
		"Your sentiment is so polarized I feel like I'm in the South pole.",
		"That's an objective opinion, %s." % resolve_message_username(data),
		"That is the real objective truth bomb!"])


def format_subjective(sentiment, data):
	op = resolve_message_username(data)
	return random.choice([
		"That was very personal, %s." % op,
		"I sense subjectivity.",
		"That is only your personal opinion, %s! (However I do not have enough data points as to whether it is right)." % op,
		"Heart-metling, %s, though lacking a strong view point. Having a strong opinion is a core value at Adatao, YKR?!?" % op,
		])

def response(original_msg_data, response):
	if DEBUG:
		logging.info("RESPONSE %s TO ORIGINAL MSG (%s)" % (response, original_msg_data))
	else:
		global outputs
		outputs.append((original_msg_data['channel'], response))

def process_message(data):
	try:
		if data['user'] == 'U0494H7FR':
			# ignoring myself
			return
		t = TextBlob(data['text'])
		data['sentiment'] = t.sentiment
		if 'justabot' in data['text'] or 'U0494H7FR' in data['text']:
			if data['type'] == 'bot_message':
				response(random.choice(['You are just a bot, your sentiment is fake.', 'You are just a bot, your words are manufactured.']))
			else:
				response(data, signature_message())
		if abs(t.sentiment.polarity) >= 0.5:
			if t.sentiment.subjectivity >= 0.65:
				response(data, format_polarized_subjective(t.sentiment, data))
			else:
				response(data, format_polarized(t.sentiment, data))
		elif t.sentiment.subjectivity > 0.65:
			response(data, format_subjective(t.sentiment, data))

		username = resolve_message_username(data)
		if username in BOT_STATE.users_avg_polarity:			
			x = BOT_STATE.users_avg_polarity[username]
			x['sum'] += abs(t.sentiment.polarity)
			x['count'] += 1
			BOT_STATE.users_avg_polarity[username] = x
		else:
			BOT_STATE.users_avg_polarity[username] = {'sum': abs(t.sentiment.polarity), 'count': 1}

		for n in t.noun_phrases:
			if n in BOT_STATE.topics_count:
				BOT_STATE.topics_count[n] += 1
			else:
				BOT_STATE.topics_count[n] = 1
		
		if re.search("opinionated", data['text']) or re.search("strongest opinion", data['text']):
			xs = [ (u, float(x['sum']) / x['count']) for u, x in BOT_STATE.users_avg_polarity.items() ]
			xs = sorted(xs, key=lambda x: x[1], reverse=True)[:10]
			userlist = ["%s. %s (avg absolute sentiment polarity %.2f)" % (i, x[0], x[1]) for i, x in enumerate(xs)]
			response(data, "The most opinionated users are: \n%s" % "\n".join(userlist))
		elif re.search("topics", data['text']):
			xs = BOT_STATE.topics_count.items()
			xs = sorted(xs, key=lambda x: x[1], reverse=True)[:10]
			topiclist = ["%s. %s (%d mentions)" % (i, x[0], x[1]) for i, x in enumerate(xs) if x[1] > 1]
			response(data, "The most often mentioned topics are: \n%s" % "\n".join(topiclist))
	except Exception as e:
		logging.error("ERROR during processing message %s" % data)
		logging.exception(e)