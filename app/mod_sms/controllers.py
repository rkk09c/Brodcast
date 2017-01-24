from datetime import datetime
from flask import request, Response
from flask_restful import Resource
from twilio import TwilioRestException

from app import app, tc, db
from app.mod_sms.adapters import MessageRequest
from app.mod_sms.models import UserGroup, User, Message

# I would like to pull this from app.mod_templates.base_message
#   but there seems to be a lookup error on Heroku
from app.mod_sms.templates import base_message


class Test(Resource):
    """Just a test to show API is running"""

    def get(self):
        return True


class BaseMessage(Resource, MessageRequest):
    """docstring for BaseMessage"""

    @staticmethod
    def save_message(parsed_request):
        # Phone number format validation
        message = Message(
            sms_message_sid=parsed_request.sms_message_sid,
            body=parsed_request.body,
            sms_status=parsed_request.sms_status,
            to_number=parsed_request.to_number,
            to_zip=parsed_request.to_zip,
            to_country=parsed_request.to_country,
            from_number=parsed_request.from_number,
            from_zip=parsed_request.from_zip,
            from_country=parsed_request.from_country
        ).create()

        user = User(phone=parsed_request.from_number).show()
        user.append_message(message)

        user_group = UserGroup(phone_number=parsed_request.to_number, active=True).show()
        user_group.append_message(message)

        message.commit()

        return user_group, user, message


class InboundMessage(BaseMessage):
    """docstring for InboundMessage"""

    def post(self):
        user_group, user, message = self.save_message(self.request())
        body = base_message(message=message, user=user, user_group=user_group)
        # TODO: add regex matching for other path than trigger_group_message
        OutboundMessage.trigger_group_message(user_group=user_group, user=user,
                                              body=body, message_sid=message.sms_message_sid)


class OutboundMessage(BaseMessage):
    """docstring for OutboundMessage"""

    @classmethod
    def trigger_group_message(cls, user_group, user, body, message_sid=None):
        users = user_group.show_users()
        users.discard(user)

        while users:
            cls.post(user_group=user_group, to_user=users.pop(), sent_from_user=user, body=body)

        resp_message = 'Message {message_sid} sent at {datetime}'.format(message_sid=message_sid, datetime=str(datetime.now())))
        return Response(resp_message, content_type='text/xml; charset=utf-8')

    @staticmethod
    def post(user_group, to_users, from_user, body):
        if to_user.active:
            try:
                tc.messages.create(
                    to=user.phone,
                    from_=user_group.phone_number,
                    body=body,
                    # media_url=
                )
            except TwilioRestException as e:
                print(e)
            except Exception as other_exception:
                print(other_exception)
