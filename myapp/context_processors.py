def user_context(request):
    return {
        'username': request.session.get('username', 'Guest')
    }
