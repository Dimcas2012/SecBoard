(function($) {
    $(document).ready(function() {
        var $useHtml = $('#id_use_html');
        var $content = $('#id_content').closest('.form-row');
        var $htmlContent = $('#id_html_content').closest('.form-row');

        function toggleFields() {
            if ($useHtml.is(':checked')) {
                $content.hide();
                $htmlContent.show();
            } else {
                $content.show();
                $htmlContent.hide();
            }
        }

        $useHtml.change(toggleFields);
        toggleFields();  // Call on page load

        // Preview YouTube video
        var $youtubeId = $('#id_youtube_id');
        var $previewBtn = $('<button type="button" class="button">Preview YouTube Video</button>');
        $youtubeId.after($previewBtn);

        $previewBtn.click(function(e) {
            e.preventDefault();
            var videoId = $youtubeId.val();
            if (videoId) {
                var embedUrl = 'https://www.youtube.com/embed/' + videoId;
                var $preview = $('<iframe width="560" height="315" frameborder="0" allowfullscreen></iframe>').attr('src', embedUrl);
                $youtubeId.after($preview);
            } else {
                alert('Please enter a YouTube Video ID');
            }
        });
    });
})(django.jQuery);