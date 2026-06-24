document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.cabinet-test-ad-btn').forEach(function(button) {
        button.addEventListener('click', function() {
            cabinetTestAdConnection(this);
        });
    });
    var style = document.createElement('style');
    style.textContent = [
        '.cabinet-test-ad-btn { background-color: #417690; border: none; border-radius: 4px; color: white; cursor: pointer; padding: 5px 10px; margin: 5px 0; font-size: 12px; }',
        '.cabinet-test-ad-btn:hover { background-color: #205067; }',
        '.cabinet-test-ad-btn:disabled { background-color: #89a5b5; cursor: not-allowed; }',
        '.connection-notification { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 4px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); z-index: 10000; max-width: 400px; }',
        '.notification-success { background-color: #dff0d8; border-left: 4px solid #5cb85c; color: #3c763d; }',
        '.notification-error { background-color: #f2dede; border-left: 4px solid #d9534f; color: #a94442; }',
        '.notification-warning { background-color: #fcf8e3; border-left: 4px solid #f0ad4e; color: #8a6d3b; }',
        '.close-notification { float: right; cursor: pointer; font-weight: bold; margin-left: 10px; }'
    ].join(' ');
    if (!document.querySelector('#cabinet-test-ad-style')) {
        style.id = 'cabinet-test-ad-style';
        document.head.appendChild(style);
    }
});

function cabinetTestAdConnection(button) {
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Testing...';

    let csrfToken = '';
    const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfElement) {
        csrfToken = csrfElement.value;
    } else {
        csrfToken = getCookie('csrftoken');
    }

    const url = button.getAttribute('data-url');
    if (!url) {
        button.disabled = false;
        button.textContent = originalText;
        cabinetShowNotification('Error', 'Missing test URL', 'error');
        return;
    }

    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json'
        }
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        button.disabled = false;
        button.textContent = originalText;
        if (data.status === 'success') {
            cabinetShowNotification('Success', data.message, 'success');
        } else if (data.status === 'warning') {
            cabinetShowNotification('Warning', data.message, 'warning');
        } else {
            cabinetShowNotification('Error', data.message || 'Connection test failed', 'error');
        }
    })
    .catch(function(error) {
        button.disabled = false;
        button.textContent = originalText;
        cabinetShowNotification('Error', 'Connection test failed: ' + error, 'error');
    });
}

function cabinetShowNotification(title, message, type) {
    const notification = document.createElement('div');
    notification.classList.add('connection-notification', 'notification-' + type);
    notification.innerHTML = '<strong>' + title + '</strong>: ' + message + ' <span class="close-notification">&times;</span>';
    document.body.appendChild(notification);
    const closeButton = notification.querySelector('.close-notification');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            notification.remove();
        });
    }
    setTimeout(function() {
        if (document.body.contains(notification)) {
            notification.remove();
        }
    }, 5000);
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
