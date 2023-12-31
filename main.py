from functools import wraps
import os
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, commentForm
from flask_gravatar import Gravatar

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager.init_app(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


##CONFIGURE TABLES

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)

    posts = relationship("BlogPost", back_populates="author")

    comments = relationship("Comment", back_populates="comment_author")

    def __init__(self, email, password, name):
        self.email = email
        self.password = password
        self.name = name

    def get_id(self):
        return str(self.email)


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments=relationship("Comment",back_populates="parent_post")


class Comment(db.Model):
    __tablename__="comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    text = db.Column(db.String(400))
    post_id=db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    comment_author = relationship("User", back_populates="comments")
    parent_post=relationship("BlogPost",back_populates="comments")


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)

        return f(*args, **kwargs)

    return decorated_function


with app.app_context():
    # db.create_all()



    @app.route('/')
    def get_all_posts():
        posts = BlogPost.query.all()
        return render_template("index.html", all_posts=posts, login=current_user)


    @app.route('/register', methods=["POST", "GET"])
    def register():
        form = RegisterForm()

        if form.validate_on_submit():
            enter_email = form.email.data
            if enter_email in all_email_list():
                flash("An account with this email already exist,log in instead")
                return redirect(url_for("login"))

            hash_and_salted_password = generate_password_hash(
                form.password.data,
                method='pbkdf2:sha256',
                salt_length=8)

            new_user = User(email=form.email.data, password=hash_and_salted_password, name=form.name.data)
            db.session.add(new_user)
            db.session.commit()
            user = load_user(enter_email)
            login_user(user)

            return redirect("/")

        return render_template("register.html", form=form, login=current_user)


    @app.route('/login', methods=["POST", "GET"])
    def login():
        login_form = LoginForm()
        if request.method == "POST":
            user_email = request.form.get("email")
            password_user = request.form.get("password")

            if user_email in all_email_list():
                user = db.session.execute(db.select(User).filter_by(email=user_email)).scalar_one()

                if check_password_hash(password=password_user, pwhash=user.password):

                    user = load_user(user_email)
                    login_user(user)
                    flash("You have logged in ")
                    return redirect("/")
                else:
                    flash("Password enter is not correct")
                    return redirect(url_for("login"))
            else:
                flash("An account with this email don't exit")
                return redirect(url_for("login"))

        return render_template("login.html", form=login_form, login=current_user)


    @app.route('/logout')
    def logout():
        logout_user()
        flash("You have been logout")
        return redirect(url_for('get_all_posts'))


    @app.route("/post/<int:post_id>",methods=["POST","GET"])
    def show_post(post_id):
        form = commentForm()
        requested_post = BlogPost.query.get(post_id)
        if form.validate_on_submit():
            if  current_user.is_authenticated:
                comment=Comment(
                    text=form.comment.data,
                    comment_author=current_user,
                    parent_post=requested_post
                )
                db.session.add(comment)
                db.session.commit()




            else:
                flash("kindly login again")
                redirect(url_for("login"))


        return render_template("post.html", post=requested_post, login=current_user, comment=form,gravatar=gravatar)


    @app.route("/about")
    def about():
        return render_template("about.html", login=current_user)


    @app.route("/contact")
    def contact():
        return render_template("contact.html", login=current_user)


    @app.route("/new-post", methods=["GET", "POST"])
    @admin_only
    def add_new_post():
        form = CreatePostForm()
        if form.validate_on_submit():
            new_post = BlogPost(
                title=form.title.data,
                subtitle=form.subtitle.data,
                body=form.body.data,
                img_url=form.img_url.data,
                author=current_user,
                date=date.today().strftime("%B %d, %Y")
            )
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for("get_all_posts"))
        return render_template("make-post.html", form=form, login=current_user)


    @app.route("/edit-post/<int:post_id>")
    @admin_only
    def edit_post(post_id):
        post = BlogPost.query.get(post_id)
        edit_form = CreatePostForm(
            title=post.title,
            subtitle=post.subtitle,
            img_url=post.img_url,
            author=post.author,
            body=post.body
        )
        if edit_form.validate_on_submit():
            post.title = edit_form.title.data
            post.subtitle = edit_form.subtitle.data
            post.img_url = edit_form.img_url.data
            post.author = edit_form.author.data
            post.body = edit_form.body.data
            db.session.commit()
            return redirect(url_for("show_post", post_id=post.id))

        return render_template("make-post.html", form=edit_form)


    @app.route("/delete/<int:post_id>")
    @admin_only
    def delete_post(post_id):
        post_to_delete = BlogPost.query.get(post_id)
        db.session.delete(post_to_delete)
        db.session.commit()
        return redirect(url_for('get_all_posts'))


    @login_manager.user_loader
    def load_user(user_id):
        email = user_id
        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one()
        return user


    def all_email_list():
        all_users = db.session.query(User).all()
        the_list = [user.email for user in all_users]
        return the_list


    @login_manager.user_loader
    def load_user(user_id):
        email = user_id
        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one()
        return user




