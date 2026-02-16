/* VoiceFileUpload — file validation, preview, and upload UI.
 *
 * Reads constants and attachment state from VoiceState.
 * Zero dependencies on other voice modules.
 */
window.VoiceFileUpload = (function () {
  'use strict';

  function getFileExtension(filename) {
    if (!filename || filename.indexOf('.') === -1) return '';
    return filename.split('.').pop().toLowerCase();
  }

  function isAllowedFile(file) {
    var ext = getFileExtension(file.name);
    return VoiceState.ALLOWED_EXTENSIONS.indexOf(ext) !== -1;
  }

  function isImageFile(file) {
    return VoiceState.ALLOWED_IMAGE_TYPES.indexOf(file.type) !== -1;
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function getFileTypeIcon(filename) {
    var ext = getFileExtension(filename);
    var icons = {
      pdf: '\uD83D\uDCC4',
      txt: '\uD83D\uDCDD',
      md: '\uD83D\uDCDD',
      py: '\uD83D\uDC0D',
      js: '\uD83D\uDCDC',
      ts: '\uD83D\uDCDC',
      json: '{ }',
      yaml: '\u2699\uFE0F',
      yml: '\u2699\uFE0F',
      html: '\uD83C\uDF10',
      css: '\uD83C\uDFA8',
      rb: '\uD83D\uDC8E',
      sh: '\uD83D\uDCBB',
      sql: '\uD83D\uDDD1\uFE0F',
      csv: '\uD83D\uDCCA',
      log: '\uD83D\uDCCB',
    };
    return icons[ext] || '\uD83D\uDCC1';
  }

  function showPendingAttachment(file) {
    VoiceState.pendingAttachment = file;
    var previewEl = document.getElementById('chat-attachment-preview');
    var thumbEl = document.getElementById('attachment-thumb');
    var nameEl = document.getElementById('attachment-name');
    var sizeEl = document.getElementById('attachment-size');
    if (!previewEl || !thumbEl || !nameEl || !sizeEl) return;

    nameEl.textContent = file.name;
    sizeEl.textContent = formatFileSize(file.size);

    if (isImageFile(file)) {
      if (VoiceState.pendingBlobUrl) URL.revokeObjectURL(VoiceState.pendingBlobUrl);
      VoiceState.pendingBlobUrl = URL.createObjectURL(file);
      thumbEl.innerHTML = '<img src="' + VoiceState.pendingBlobUrl + '" alt="Preview">';
    } else {
      thumbEl.innerHTML = '<span class="file-icon">' + getFileTypeIcon(file.name) + '</span>';
    }

    previewEl.style.display = 'flex';
    hideUploadError();
  }

  function clearPendingAttachment() {
    VoiceState.pendingAttachment = null;
    if (VoiceState.pendingBlobUrl) {
      URL.revokeObjectURL(VoiceState.pendingBlobUrl);
      VoiceState.pendingBlobUrl = null;
    }
    var previewEl = document.getElementById('chat-attachment-preview');
    var thumbEl = document.getElementById('attachment-thumb');
    if (previewEl) previewEl.style.display = 'none';
    if (thumbEl) thumbEl.innerHTML = '';
  }

  function showUploadProgress(pct) {
    var progressEl = document.getElementById('chat-upload-progress');
    var barEl = document.getElementById('chat-upload-bar');
    if (progressEl) progressEl.style.display = 'block';
    if (barEl) barEl.style.width = pct + '%';
  }

  function hideUploadProgress() {
    var progressEl = document.getElementById('chat-upload-progress');
    var barEl = document.getElementById('chat-upload-bar');
    if (progressEl) progressEl.style.display = 'none';
    if (barEl) barEl.style.width = '0%';
  }

  function showUploadError(msg) {
    var el = document.getElementById('chat-upload-error');
    if (el) {
      el.textContent = msg;
      el.style.display = 'block';
    }
  }

  function hideUploadError() {
    var el = document.getElementById('chat-upload-error');
    if (el) el.style.display = 'none';
  }

  function validateFileClientSide(file) {
    if (!isAllowedFile(file)) {
      var ext = getFileExtension(file.name);
      return 'File type .' + ext + ' is not supported. Accepted: ' + VoiceState.ALLOWED_EXTENSIONS.join(', ');
    }
    if (file.size > VoiceState.MAX_FILE_SIZE) {
      return 'File too large (' + formatFileSize(file.size) + '). Maximum: ' + formatFileSize(VoiceState.MAX_FILE_SIZE);
    }
    return null;
  }

  function handleFileDrop(file) {
    var error = validateFileClientSide(file);
    if (error) {
      showUploadError(error);
      return;
    }
    showPendingAttachment(file);
  }

  return {
    getFileExtension: getFileExtension,
    isAllowedFile: isAllowedFile,
    isImageFile: isImageFile,
    formatFileSize: formatFileSize,
    getFileTypeIcon: getFileTypeIcon,
    showPendingAttachment: showPendingAttachment,
    clearPendingAttachment: clearPendingAttachment,
    showUploadProgress: showUploadProgress,
    hideUploadProgress: hideUploadProgress,
    showUploadError: showUploadError,
    hideUploadError: hideUploadError,
    validateFileClientSide: validateFileClientSide,
    handleFileDrop: handleFileDrop
  };
})();
