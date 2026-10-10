
var checkout = {};

$(document).ready(function() {
  var $messages = $('.messages-content');
  var d, m;
  var i = 0;

  // API Gateway endpoint
  var API_URL =
    'https://a87u3kn1k2.execute-api.us-east-1.amazonaws.com/dev/chatbot';

  // Keep the same session across messages in this page
  var sessionId =
    'web-' + Date.now() + '-' +
    Math.random().toString(36).substring(2, 10);

  // Initialize chat UI
  $(window).on('load', function() {
    if ($.fn.mCustomScrollbar) {
      $messages.mCustomScrollbar();
    }
  });

  // Scroll to the latest message
  function updateScrollbar() {
    if ($.fn.mCustomScrollbar) {
      $messages
        .mCustomScrollbar('update')
        .mCustomScrollbar('scrollTo', 'bottom', {
          scrollInertia: 10,
          timeout: 0
        });
    } else {
      var element = $messages[0];
      if (element) {
        element.scrollTop = element.scrollHeight;
      }
    }
  }

  // Add timestamp to the latest message
  function setDate() {
    d = new Date();

    if (m !== d.getMinutes()) {
      m = d.getMinutes();

      $('<div class="timestamp"></div>')
        .text(d.getHours() + ':' + String(m).padStart(2, '0'))
        .appendTo($('.message:last'));
    }
  }

  // Parse the different response formats API Gateway may return
  function normalizeResponse(response) {
    var data = response;

    // Handle jQuery AJAX response wrapper if present
    if (data && data.data !== undefined &&
        data.status !== undefined) {
      data = data.data;
    }

    // Handle Lambda proxy integration responses
    if (data && typeof data.body === 'string') {
      try {
        data = JSON.parse(data.body);
      } catch (error) {
        console.error('Could not parse response body:', data.body);
        throw error;
      }
    } else if (data && data.body &&
               typeof data.body === 'object') {
      data = data.body;
    }

    return data;
  }

  // Send a message to API Gateway -> Lambda -> Lex
  function callChatbotApi(message) {
    var payload = {
      userId: sessionId,
      messages: [{
        type: 'text',
        unstructured: {
          text: message
        }
      }]
    };

    console.log('Sending chatbot request:', payload);

    return $.ajax({
      url: API_URL,
      type: 'POST',
      contentType: 'application/json',
      dataType: 'json',
      data: JSON.stringify(payload)
    }).then(function(response) {
      console.log('Raw API response:', response);

      var data = normalizeResponse(response);

      console.log('Parsed API response:', data);

      return data;
    });
  }

  // Handle a submitted user message
  function insertMessage() {
    var $input = $('.message-input');
    var msg = $input.val();

    if ($.trim(msg) === '') {
      return false;
    }

    // Display the user's message
    $('<div class="message message-personal"></div>')
      .text(msg)
      .appendTo($('.mCSB_container').length
        ? $('.mCSB_container')
        : $messages)
      .addClass('new');

    setDate();
    $input.val('');
    updateScrollbar();

    callChatbotApi(msg)
      .then(function(data) {
        if (!data || !Array.isArray(data.messages)) {
          console.error('Unexpected chatbot response format:', data);
          insertResponseMessage(
            'The chatbot returned an unexpected response. Please try again.'
          );
          return;
        }

        if (data.messages.length === 0) {
          insertResponseMessage(
            "Sorry, I couldn't understand. Please try again."
          );
          return;
        }

        data.messages.forEach(function(message) {
          var text = '';

          if (message.unstructured &&
              typeof message.unstructured.text === 'string') {
            text = message.unstructured.text;
          } else if (typeof message.text === 'string') {
            text = message.text;
          } else if (typeof message.content === 'string') {
            text = message.content;
          }

          if (text) {
            insertResponseMessage(text);
          } else {
            console.warn('Unsupported chatbot message:', message);
          }
        });
      })
      .catch(function(error) {
        console.error('Chatbot API request failed:', error);

        if (error.status !== undefined) {
          console.error('HTTP status:', error.status);
          console.error('Response body:', error.responseText);
        }

        var errorMessage =
          'Could not connect to the chatbot. Please try again.';

        if (error.status === 0) {
          errorMessage =
            'The request could not reach the API. Check the API URL and CORS settings.';
        } else if (error.status === 403) {
          errorMessage =
            'The API returned 403 Forbidden. Check the API Gateway route and permissions.';
        } else if (error.status === 404) {
          errorMessage =
            'The chatbot API route was not found. Check the stage and route URL.';
        } else if (error.status >= 500) {
          errorMessage =
            'The chatbot service encountered a server error. Check the Lambda logs.';
        }

        insertResponseMessage(errorMessage);
      });

    return true;
  }

  // Send button, if present in the page
  $('.message-submit').on('click', function() {
    insertMessage();
  });

  // Press Enter to send; Shift+Enter inserts a new line
  $(window).on('keydown', function(e) {
    if (
      e.which === 13 &&
      $(e.target).is('.message-input') &&
      !e.shiftKey
    ) {
      e.preventDefault();
      insertMessage();
      return false;
    }
  });

  // Display a chatbot response
  function insertResponseMessage(content) {
    var avatar =
      'https://media.tenor.com/images/' +
      '4c347ea7198af12fd0a66790515f958f/tenor.gif';

    var $container = $('.mCSB_container').length
      ? $('.mCSB_container')
      : $messages;

    var $loading = $(
      '<div class="message loading new">' +
        '<figure class="avatar"><img /></figure>' +
        '<span></span>' +
      '</div>'
    );

    $loading.find('img').attr('src', avatar);
    $loading.appendTo($container);
    updateScrollbar();

    setTimeout(function() {
      $loading.remove();

      var $response = $(
        '<div class="message new">' +
          '<figure class="avatar"><img /></figure>' +
        '</div>'
      );

      $response.find('img').attr('src', avatar);
      $response.append(document.createTextNode(String(content)));

      $response.appendTo($container);
      setDate();
      updateScrollbar();

      i++;
    }, 300);
  }
});
