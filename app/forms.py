from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError

from app.models import User

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign in")
    
class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    password2 = PasswordField("Repeat Password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Register")
    
    # WTForms knows to use methods called `validate_{field}` to apply
    # as validators to that field.
    def validate_username(self, username):
        """Make sure this username isn't taken."""
        user = User.query.filter_by(username=username.data).first()
        
        if user is not None:
            raise ValidationError("Please use a different username.")
    
    def validate_email(self, email):
        """Make sure this email isn't taken."""
        user = User.query.filter_by(email=email.data).first()
        
        if user is not None:
            raise ValidationError("Please use a different email.")