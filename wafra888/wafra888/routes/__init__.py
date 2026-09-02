def register_blueprints(app):
    from .auth_routes import bp as auth_bp
    from .profile_routes import bp as profile_bp
    from .chat_routes import bp as chat_bp
    from .board_routes import bp as board_bp
    from .leadership_routes import bp as leadership_bp
    from .cron_routes import bp as cron_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(board_bp)
    app.register_blueprint(leadership_bp)
    app.register_blueprint(cron_bp)
