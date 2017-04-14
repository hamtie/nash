# Copyright 2014 SolidBuilds.com. All rights reserved
#
# Authors: Ling Thio <ling.thio@gmail.com>

from datetime import datetime
from flask import Flask
from flask_mail import Mail
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from flask_sqlalchemy import SQLAlchemy
from flask_user import UserManager, SQLAlchemyAdapter
from flask_wtf.csrf import CsrfProtect

app = Flask(__name__)           # The WSGI compliant web application object
db = SQLAlchemy()               # Setup Flask-SQLAlchemy
manager = Manager(app)          # Setup Flask-Script

# Initialize Flask Application
def init_app(app, extra_config_settings={}):
    # Read common settings from 'app/settings.py'
    app.config.from_object('app.settings')

    # Read environment-specific settings from 'app/local_settings.py'
    try:
        app.config.from_object('app.local_settings')
    except ImportError:
        print("The configuration file 'app/local_settings.py' does not exist.\n"+
              "Please copy app/local_settings_example.py to app/local_settings.py\n"+
              "and customize its settings before you continue.")
        exit()

    # Add/overwrite extra settings from parameter 'extra_config_settings'
    app.config.update(extra_config_settings)
    if app.testing:
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF checks while testing

    # Initialize Flask-SQLAlchemy and Flask-Script _after_ app.config has been read
    db.init_app(app)

    # Setup Flask-Migrate
    migrate = Migrate(app, db)
    manager.add_command('db', MigrateCommand)

    # Setup Flask-Mail
    mail = Mail(app)

    # Setup WTForms CsrfProtect
    #CsrfProtect(app)

    # Define bootstrap_is_hidden_field for flask-bootstrap's bootstrap_wtf.html
    from wtforms.fields import HiddenField

    def is_hidden_field_filter(field):
        return isinstance(field, HiddenField)

    app.jinja_env.globals['bootstrap_is_hidden_field'] = is_hidden_field_filter

    # Setup an error-logger to send emails to app.config.ADMINS
    init_email_error_handler(app)

    # Setup Flask-User to handle user account related forms
    from app.models import User, MyRegisterForm
    from app.views import user_profile_page

    db_adapter = SQLAlchemyAdapter(db, User)  # Setup the SQLAlchemy DB Adapter
    user_manager = UserManager(db_adapter, app,  # Init Flask-User and bind to app
                               register_form=MyRegisterForm,  # using a custom register form with UserProfile fields
                               user_profile_view_function=user_profile_page,
    )

    import app.manage_commands


def init_email_error_handler(app):
    """
    Initialize a logger to send emails on error-level messages.
    Unhandled exceptions will now send an email message to app.config.ADMINS.
    """
    if app.debug: return  # Do not send error emails while developing

    # Retrieve email settings from app.config
    host = app.config['MAIL_SERVER']
    port = app.config['MAIL_PORT']
    from_addr = app.config['MAIL_DEFAULT_SENDER']
    username = app.config['MAIL_USERNAME']
    password = app.config['MAIL_PASSWORD']
    secure = () if app.config.get('MAIL_USE_TLS') else None

    # Retrieve app settings from app.config
    to_addr_list = app.config['ADMINS']
    subject = app.config.get('APP_SYSTEM_ERROR_SUBJECT_LINE', 'System Error')

    # Setup an SMTP mail handler for error-level messages
    import logging
    from logging.handlers import SMTPHandler

    mail_handler = SMTPHandler(
        mailhost=(host, port),  # Mail host and port
        fromaddr=from_addr,  # From address
        toaddrs=to_addr_list,  # To address
        subject=subject,  # Subject line
        credentials=(username, password),  # Credentials
        secure=secure,
    )
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

    # Log errors using: app.logger.error('Some error message')

## via https://gist.githubusercontent.com/alanhamlett/6604662/raw/41d0db0f05aa6b156a7a090223c528cc509a6713/api.py
class Model(db.Model):
    """Base SQLAlchemy Model for automatic serialization and
    deserialization of columns and nested relationships.

    Usage::

        >>> class User(Model):
        >>>     id = db.Column(db.Integer(), primary_key=True)
        >>>     email = db.Column(db.String(), index=True)
        >>>     name = db.Column(db.String())
        >>>     password = db.Column(db.String())
        >>>     posts = db.relationship('Post', backref='user', lazy='dynamic')
        >>>     ...
        >>>     default_fields = ['email', 'name']
        >>>     hidden_fields = ['password']
        >>>     readonly_fields = ['email', 'password']
        >>>
        >>> class Post(Model):
        >>>     id = db.Column(db.Integer(), primary_key=True)
        >>>     user_id = db.Column(db.String(), db.ForeignKey('user.id'), nullable=False)
        >>>     title = db.Column(db.String())
        >>>     ...
        >>>     default_fields = ['title']
        >>>     readonly_fields = ['user_id']
        >>>
        >>> model = User(email='john@localhost')
        >>> db.session.add(model)
        >>> db.session.commit()
        >>>
        >>> # update name and create a new post
        >>> validated_input = {'name': 'John', 'posts': [{'title':'My First Post'}]}
        >>> model.set_columns(**validated_input)
        >>> db.session.commit()
        >>>
        >>> print(model.to_dict(show=['password', 'posts']))
        >>> {u'email': u'john@localhost', u'posts': [{u'id': 1, u'title': u'My First Post'}], u'name': u'John', u'id': 1}
    """
    __abstract__ = True

    # Stores changes made to this model's attributes. Can be retrieved
    # with model.changes
    _changes = {}

    def __init__(self, **kwargs):
        kwargs['_force'] = True
        self._set_columns(**kwargs)

    def _set_columns(self, **kwargs):
        force = kwargs.get('_force')

        readonly = []
        if hasattr(self, 'readonly_fields'):
            readonly = self.readonly_fields
        if hasattr(self, 'hidden_fields'):
            readonly += self.hidden_fields

        readonly += [
            'id',
            'created',
            'updated',
            'modified',
            'created_at',
            'updated_at',
            'modified_at',
        ]

        changes = {}

        columns = self.__table__.columns.keys()
        relationships = self.__mapper__.relationships.keys()

        for key in columns:
            allowed = True if force or key not in readonly else False
            exists = True if key in kwargs else False
            if allowed and exists:
                val = getattr(self, key)
                if val != kwargs[key]:
                    changes[key] = {'old': val, 'new': kwargs[key]}
                    setattr(self, key, kwargs[key])

        for rel in relationships:
            allowed = True if force or rel not in readonly else False
            exists = True if rel in kwargs else False
            if allowed and exists:
                is_list = self.__mapper__.relationships[rel].uselist
                if is_list:
                    valid_ids = []
                    query = getattr(self, rel)
                    cls = self.__mapper__.relationships[rel].argument()
                    for item in kwargs[rel]:
                        if 'id' in item and query.filter_by(id=item['id']).limit(1).count() == 1:
                            obj = cls.query.filter_by(id=item['id']).first()
                            col_changes = obj.set_columns(**item)
                            if col_changes:
                                col_changes['id'] = str(item['id'])
                                if rel in changes:
                                    changes[rel].append(col_changes)
                                else:
                                    changes.update({rel: [col_changes]})
                            valid_ids.append(str(item['id']))
                        else:
                            col = cls()
                            col_changes = col.set_columns(**item)
                            query.append(col)
                            db.session.flush()
                            if col_changes:
                                col_changes['id'] = str(col.id)
                                if rel in changes:
                                    changes[rel].append(col_changes)
                                else:
                                    changes.update({rel: [col_changes]})
                            valid_ids.append(str(col.id))

                    # delete related rows that were not in kwargs[rel]
                    for item in query.filter(not_(cls.id.in_(valid_ids))).all():
                        col_changes = {
                            'id': str(item.id),
                            'deleted': True,
                        }
                        if rel in changes:
                            changes[rel].append(col_changes)
                        else:
                            changes.update({rel: [col_changes]})
                        db.session.delete(item)

                else:
                    val = getattr(self, rel)
                    if self.__mapper__.relationships[rel].query_class is not None:
                        if val is not None:
                            col_changes = val.set_columns(**kwargs[rel])
                            if col_changes:
                                changes.update({rel: col_changes})
                    else:
                        if val != kwargs[rel]:
                            setattr(self, rel, kwargs[rel])
                            changes[rel] = {'old': val, 'new': kwargs[rel]}

        return changes

    def set_columns(self, **kwargs):
        self._changes = self._set_columns(**kwargs)
        if 'modified' in self.__table__.columns:
            self.modified = datetime.utcnow()
        if 'updated' in self.__table__.columns:
            self.updated = datetime.utcnow()
        if 'modified_at' in self.__table__.columns:
            self.modified_at = datetime.utcnow()
        if 'updated_at' in self.__table__.columns:
            self.updated_at = datetime.utcnow()
        return self._changes

    @property
    def changes(self):
        return self._changes

    def reset_changes(self):
        self._changes = {}

    def to_dict(self, show=None, hide=None, path=None, show_all=None):
        """ Return a dictionary representation of this model.
        """

        if not show:
            show = []
        if not hide:
            hide = []
        hidden = []
        if hasattr(self, 'hidden_fields'):
            hidden = self.hidden_fields
        default = []
        if hasattr(self, 'default_fields'):
            default = self.default_fields

        ret_data = {}

        if not path:
            path = self.__tablename__.lower()
            def prepend_path(item):
                item = item.lower()
                if item.split('.', 1)[0] == path:
                    return item
                if len(item) == 0:
                    return item
                if item[0] != '.':
                    item = '.%s' % item
                item = '%s%s' % (path, item)
                return item
            show[:] = [prepend_path(x) for x in show]
            hide[:] = [prepend_path(x) for x in hide]

        columns = self.__table__.columns.keys()
        relationships = self.__mapper__.relationships.keys()
        properties = dir(self)

        for key in columns:
            check = '%s.%s' % (path, key)
            if check in hide or key in hidden:
                continue
            if show_all or key is 'id' or check in show or key in default:
                ret_data[key] = getattr(self, key)

        for key in relationships:
            check = '%s.%s' % (path, key)
            if check in hide or key in hidden:
                continue
            if show_all or check in show or key in default:
                hide.append(check)
                is_list = self.__mapper__.relationships[key].uselist
                if is_list:
                    ret_data[key] = []
                    for item in getattr(self, key):
                        ret_data[key].append(item.to_dict(
                            show=show,
                            hide=hide,
                            path=('%s.%s' % (path, key.lower())),
                            show_all=show_all,
                        ))
                else:
                    if self.__mapper__.relationships[key].query_class is not None:
                        ret_data[key] = getattr(self, key).to_dict(
                            show=show,
                            hide=hide,
                            path=('%s.%s' % (path, key.lower())),
                            show_all=show_all,
                        )
                    else:
                        ret_data[key] = getattr(self, key)

        for key in list(set(properties) - set(columns) - set(relationships)):
            if key.startswith('_'):
                continue
            check = '%s.%s' % (path, key)
            if check in hide or key in hidden:
                continue
            if show_all or check in show or key in default:
                val = getattr(self, key)
                try:
                    ret_data[key] = json.loads(json.dumps(val))
                except:
                    pass

        return ret_data
