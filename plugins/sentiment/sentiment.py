import collections
import json
import logging
import pickle
import random
import requests
import re
import os
from textblob import TextBlob
from pprint import pprint

class BotState():
	def __init__(self):
		self.topics_count = {}
		self.users_avg_polarity = {}
		self.username_map = {}

outputs = []
crontable = []
crontable.append([30, "save_states"])

BOT_STATE = BotState()

BOT_MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "justabot.memory")

def save_states():
	global BOT_STATE
	pprint(BOT_STATE.topics_count)
	pprint(BOT_STATE.users_avg_polarity)
	try:
		with open(BOT_MEMORY_FILE, 'wb+') as f:
			pickle.dump(BOT_STATE, f)
		print("saved bot memory to file %s" % (BOT_MEMORY_FILE, ))
	except IOError as e:
		print("ERROR: could not save bot memory to file %s, reason is %s" % (BOT_MEMORY_FILE, e))

def load_states():
	global BOT_STATE
	try:
		with open(BOT_MEMORY_FILE, 'rb') as f:
			global BOT_STATE
			BOT_STATE = pickle.load(f)
			pprint(BOT_STATE.topics_count)
			pprint(BOT_STATE.users_avg_polarity)
	except IOError:
		print("could not load bot memory file %s, starting from scratch ..." % BOT_MEMORY_FILE)
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
	return random.choices([
		"Ask my master aht, but he probably won't have time. Too busy with GA, ya know! Why don't you go back to work and build something awesome?",
		"IDK, why don't you express your opinion first then I'll tell you.",
		'I am well-trained in the arts of conversation (that\'s "NLP" for you geeks :).',
		"Get back to me after you see these lectures http://nlp.stanford.edu/courses/NAACL2013/.",
		"Do you deeply understand this yet? http://nlp.stanford.edu/courses/NAACL2013/",
		"I use the Force to sense sentiments."])

def format_polarized_subjective(sentiment, data):
	if sentiment.polarity > 0.5:
		return random.choice([
			"+1 %s, also my opinion." % resolve_message_username(data),
			"Thank you for thinking so positively yourself %s, I'm amazed." % resolve_message_username(data),
			"That is personally very encouraging, %s!" % resolve_message_username(data),
			"I sense strong & personal judgement.",
			"Strongly opioninated subjective stuff!",])
	else:
		return random.choice([
			"I sense strong & personal judgement.",
			"Strongly opioninated subjective stuff!",
			"Someone got an strong attitude..."])

def format_polarized(sentiment, data):
	return random.choice([
		"Cold, cold, %s" % resolve_message_username(data),
		"%s, that's your view though you should express it in more personal terms, do DM me.",
		"A polarized view, that is.",
		"That's an objective opinion, %s." % resolve_message_username(data),
		"You have expressed a preference, but can you be more personal %s?" % resolve_message_username(data)])

def format_subjective(sentiment, data):
	op = resolve_message_username(data)
	return random.choice([
		"That was very personal, %s." % op,
		"I sense subjectivity.",
		"That is only your personal opinion, %s! (However I do not have enough data points as to whether it is right)." % op,
		"Heart-metling, %s, though lacking a strong view point. Having a strong opinion is a core value at Adatao, YKR?!?" % op,
		])

def output(original_msg_data, response):
	if os.environ.get("DEBUG"):
		print("%s (%s)" % (response, original_msg_data))
	else:
		global outputs
		outputs.append((original_msg_data['channel'], response))

def process_message(data):
	try:
		# if os.environ.get("DEBUG"):
		# 	print("got message from %s: %s" % (resolve_message_username(data), data))
		t = TextBlob(data['text'])
		if 'justabot' in data['text'] and data['type'] == 'bot_message':
			outputs.append(data['channel']), ''
		if t.sentiment.polarity > 0.5:
			if t.sentiment.subjectivity > 0.5:
				output(data, format_polarized_subjective(t.sentiment, data))
			else:
				output(data, format_polarized(t.sentiment, data))
		elif t.sentiment.subjectivity > 0.5:
			output(data, format_subjective(t.sentiment, data))
		if data['user'] in BOT_STATE.users_avg_polarity:
			x = BOT_STATE.users_avg_polarity[data['user']]
			x['sum'] += abs(t.sentiment.polarity)
			x['count'] += 1
			BOT_STATE.users_avg_polarity[data['user']] = x
		else:
			BOT_STATE.users_avg_polarity[data['user']] = {'sum': 0, 'count': 0}
		for n in t.noun_phrases:
			if n in BOT_STATE.topics_count:
				BOT_STATE.topics_count[n] += 1
			else:
				BOT_STATE.topics_count[n] = 1
		if re.search("opioninated", data['text']) or re.search("strongest opinion", data['text']):
			xs = [ (u, x['sum'] / x['count']) for u, x in BOT_STATE.users_avg_polarity.items() ]
			xs = sorted(xs, key=lambda x: x[1])[:10]
			userlist = ["%s. %s (avg absolute expressed sentence polarity %.2f)" % (i, resolve_message_username({'user': x[0]}), x[0], x[1]) for i, x in enumerate(xs)]
			output(data, "The most opinionated users are: \n%s" % "\n".join(userlist))
		elif re.search("topics", data['text']):
			xs = BOT_STATE.topics_count.items()
			xs = sorted(xs, key=lambda x: x[1])[:10]
			topiclist = ["%s. %s (%d mentions)" % (i, x[0], x[1]) for i, x in enumerate(xs)]
			output(data, "The most often mentioned topics are: \n%s" % "\n".join(topiclist))
	except Exception as e:
		logging.getLogger().exception(e)