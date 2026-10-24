from app import create_app
app = create_app()
if __name__ == '__main__':
    # Avoid the development reloader/debugger process on newer Python releases.
    app.run(host='127.0.0.1', port=5000, debug=False)
