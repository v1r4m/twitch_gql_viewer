import socket, re, json, argparse, emoji, csv, time
from decouple import config
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from configparser import ConfigParser


class DefaultUser(Exception):
	"""Raised when you try send a message with the default user"""
	pass

class CallbackFunction(Exception):
	"""Raised when the callback function does not have (only) one required positional argument"""
	pass

class TwitchChatIRC():
	__HOST = 'irc.chat.twitch.tv'
	__DEFAULT_NICK = 'justinfan67420'
	__DEFAULT_PASS = 'SCHMOOPIIE'
	__PORT = 80

	__PATTERN = re.compile(r'@(.+?(?=\s+:)).*PRIVMSG[^:]*:([^\r\n]*)')

	__CURRENT_CHANNEL = None

	def __init__(self, username = None, password = None):
		# try get from environment variables (.env)
		self.__NICK = config('NICK', self.__DEFAULT_NICK)
		self.__PASS = config('PASS', self.__DEFAULT_PASS)

		# overwrite if specified
		if(username is not None):
			self.__NICK = username
		if(password is not None):
			self.__PASS = 'oauth:'+str(password).lstrip('oauth:')
		
		# create new socket
		self.__SOCKET = socket.socket()
		
		# start connection
		self.__SOCKET.connect((self.__HOST, self.__PORT))
		print('Connected to',self.__HOST,'on port',self.__PORT)

		# log in
		self.__send_raw('CAP REQ :twitch.tv/tags')
		self.__send_raw('PASS ' + self.__PASS)
		self.__send_raw('NICK ' + self.__NICK)
	
	def __send_raw(self, string):
		self.__SOCKET.send((string+'\r\n').encode('utf-8'))

	def __print_message(self, message):
		config = ConfigParser()
		config.read('conf.ini')
		if message['display-name'] == config['victim']['nickname']:
			sender_email = config['email']['gmail_send']
			sender_password = config['email']['gmail_key']
			receiver_email = config['email']['email_recv']
			smtp_server = "smtp.gmail.com"
			smtp_port = 587
			subject = "Chat from "+config['victim']['nickname']
			body = '['+message['tmi-sent-ts']+']'+message['display-name']+':'+emoji.demojize(message['message']).encode('utf-8').decode('utf-8','ignore')
			message = MIMEMultipart()
			message["From"] = sender_email
			message["To"] = receiver_email
			message["Subject"] = subject
			message.attach(MIMEText(body, "plain"))
			try:
				server = smtplib.SMTP(smtp_server, smtp_port)
				server.starttls() 
				server.login(sender_email, sender_password)
				server.sendmail(sender_email, receiver_email, message.as_string())
				server.quit()
			except Exception as e:
				print("An Error occurred while sending the email: ", str(e))
		#else:
			#print('['+message['tmi-sent-ts']+']',message['display-name']+':',emoji.demojize(message['message']).encode('utf-8').decode('utf-8','ignore'))

	def __recvall(self, buffer_size):
		data = b''
		while True:
			part = self.__SOCKET.recv(buffer_size)
			data += part
			if len(part) < buffer_size:
				break
		return data.decode('utf-8')#,'ignore'

	def __join_channel(self,channel_name):
		channel_lower = channel_name.lower()

		if(self.__CURRENT_CHANNEL != channel_lower):
			self.__send_raw('JOIN #{}'.format(channel_lower))
			self.__CURRENT_CHANNEL = channel_lower

	def is_default_user(self):
		return self.__NICK == self.__DEFAULT_NICK

	def close_connection(self):
		self.__SOCKET.close()
		print('Connection closed')

	def listen(self, channel_name, messages = [], timeout=None, message_timeout=1.0, on_message = None, buffer_size = 4096, message_limit = None, output=None):
		self.__join_channel(channel_name)
		self.__SOCKET.settimeout(message_timeout)

		if(on_message is None):
			on_message = self.__print_message
		
		print('Begin retrieving messages:')

		time_since_last_message = 0
		readbuffer = ''
		startTime = time.time()
		try:
			while time.time()-startTime < 300:
				try:
					new_info = self.__recvall(buffer_size)
					readbuffer += new_info
					
					if('PING :tmi.twitch.tv' in readbuffer):
						self.__send_raw('PONG :tmi.twitch.tv')

					matches = list(self.__PATTERN.finditer(readbuffer))

					if(matches):
						time_since_last_message = 0

						if(len(matches) > 1):
							matches = matches[:-1] # assume last one is incomplete

						last_index = matches[-1].span()[1]
						readbuffer = readbuffer[last_index:]

						for match in matches:
							data = {}
							for item in match.group(1).split(';'):
								keys = item.split('=',1)
								data[keys[0]]=keys[1]
							data['message'] = match.group(2)

							messages.append(data)

							if(callable(on_message)):
								try:
									on_message(data)
								except TypeError:
									raise Exception('Incorrect number of parameters for function '+on_message.__name__)
							
							if(message_limit is not None and len(messages) >= message_limit):
								return messages
							
				except socket.timeout:
					if(timeout != None):
						time_since_last_message += message_timeout
					
						if(time_since_last_message >= timeout):
							print('No data received in',timeout,'seconds. Timing out.')
							break
		
		except KeyboardInterrupt:
			print('Interrupted by user.')
			
		except Exception as e:
			print('Unknown Error:',e)
			raise e		
		
		return messages

	def send(self, channel_name, message):
		self.__join_channel(channel_name)
 
		# check that is using custom login, not default
		if(self.is_default_user()):
			raise DefaultUser
		else:
			self.__send_raw('PRIVMSG #{} :{}'.format(channel_name.lower(),message))
			print('Sent "{}" to {}'.format(message,channel_name))