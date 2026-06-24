// Quiz admin JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a quiz admin page
    var passingScoreField = document.getElementById('id_passing_score');
    if (passingScoreField) {
        var totalScore = window.QUIZ_TOTAL_SCORE || 0;
        var label = passingScoreField.closest('.form-row').querySelector('label');
        if (label) {
            var span = document.createElement('span');
            span.className = 'total-score';
            span.textContent = ' (Total Score: ' + totalScore + ')';
            label.appendChild(span);
        }
    }
});