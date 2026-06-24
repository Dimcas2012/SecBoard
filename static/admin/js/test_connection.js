document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners to all test connection buttons
    document.querySelectorAll('.test-connection-btn').forEach(function(button) {
        button.addEventListener('click', function() {
            testConnection(this);
        });
    });
});

function testConnection(button) {
    // Disable button and show loading state
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Testing...';
    
    // Try to get CSRF token - may not be available in some contexts
    let csrfToken = '';
    const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfElement) {
        csrfToken = csrfElement.value;
    } else {
        // Try to get from cookie as a fallback
        csrfToken = getCookie('csrftoken');
    }
    
    // Get provider and ID from data attributes
    const provider = button.getAttribute('data-provider');
    const id = button.getAttribute('data-id');
    
    // Get current language from URL or default to 'en'
    let language = 'en';
    const pathParts = window.location.pathname.split('/');
    if (pathParts.length > 1 && /^(en|ru|uk)$/.test(pathParts[1])) {
        language = pathParts[1];
    }
    
    // Define URL for the connection test - include language prefix
    const url = `/${language}/app_ai/test-connection/${provider}/${id}/`;
    
    // Make AJAX request
    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Reset button state
        button.disabled = false;
        button.textContent = originalText;
        
        // Show appropriate notification
        if (data.status === 'success') {
            showNotification('Success', data.message, 'success');
        } else if (data.status === 'warning') {
            showNotification('Warning', data.message, 'warning');
        } else {
            showNotification('Error', data.message, 'error');
        }
    })
    .catch(error => {
        // Reset button state
        button.disabled = false;
        button.textContent = originalText;
        
        // Show error notification
        showNotification('Error', 'Connection test failed: ' + error, 'error');
    });
}

function showNotification(title, message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.classList.add('connection-notification', `notification-${type}`);
    
    // Add content
    notification.innerHTML = `
        <strong>${title}</strong>: ${message}
        <span class="close-notification">&times;</span>
    `;
    
    // Add to document body
    document.body.appendChild(notification);
    
    // Add close functionality - check if element exists first
    const closeButton = notification.querySelector('.close-notification');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            notification.remove();
        });
    }
    
    // Auto-remove after 5 seconds
    setTimeout(function() {
        if (document.body.contains(notification)) {
            notification.remove();
        }
    }, 5000);
}

// Helper function to get cookies (for CSRF token)
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Add CSS styles for the notifications
document.addEventListener('DOMContentLoaded', function() {
    const style = document.createElement('style');
    style.textContent = `
        .test-connection-btn {
            background-color: #417690;
            border: none;
            border-radius: 4px;
            color: white;
            cursor: pointer;
            padding: 5px 10px;
            margin: 5px 0;
            font-size: 12px;
        }
        
        .test-connection-btn:hover {
            background-color: #205067;
        }
        
        .test-connection-btn:disabled {
            background-color: #89a5b5;
            cursor: not-allowed;
        }
        
        .connection-notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            z-index: 1000;
            max-width: 400px;
            animation: slide-in 0.3s ease-out;
        }
        
        @keyframes slide-in {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        .notification-success {
            background-color: #dff0d8;
            border-left: 4px solid #5cb85c;
            color: #3c763d;
        }
        
        .notification-warning {
            background-color: #fcf8e3;
            border-left: 4px solid #f0ad4e;
            color: #8a6d3b;
        }
        
        .notification-error {
            background-color: #f2dede;
            border-left: 4px solid #d9534f;
            color: #a94442;
        }
        
        .close-notification {
            float: right;
            cursor: pointer;
            font-weight: bold;
            margin-left: 10px;
        }
    `;
    document.head.appendChild(style);
}); 