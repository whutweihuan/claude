(function () {
  "use strict";

  var CSRF_HEADERS = { "X-Requested-With": "shareFile" };
  var MAX_ACTIVE_UPLOADS = 3;
  var REFRESH_MS = 10000;
  var IMAGE_RE = /\.(jpe?g|png|gif|webp|bmp)$/i;
  var VIDEO_RE = /\.(mp4|m4v|mov|webm|avi|mkv)$/i;

  var readOnly = false;
  var activeUploads = 0;
  var pendingUploads = [];
  var refreshTimer = null;
  var imageFiles = [];
  var previewPath = null;
  var previewReturnFocus = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function setLoginError(message) {
    byId("login-error").textContent = message || "";
  }

  function formatSize(size) {
    var value = Number(size) || 0;
    if (value < 1024) {
      return value + " B";
    }
    var units = ["KB", "MB", "GB", "TB"];
    value = value / 1024;
    for (var index = 0; index < units.length; index += 1) {
      if (value < 1024 || index === units.length - 1) {
        return value.toFixed(1) + " " + units[index];
      }
      value = value / 1024;
    }
    return value.toFixed(1) + " TB";
  }

  function formatDate(timestamp) {
    if (!timestamp) {
      return "";
    }
    try {
      return new Date(timestamp * 1000).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch (error) {
      return "";
    }
  }

  function showLogin() {
    closePreview();
    byId("files-view").hidden = true;
    byId("login-view").hidden = false;
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
    byId("pin-input").focus();
  }

  function showFiles() {
    byId("login-view").hidden = true;
    byId("files-view").hidden = false;
    loadFiles();
    if (!refreshTimer) {
      refreshTimer = setInterval(function () {
        if (document.hidden || hasActiveUploads()) {
          return;
        }
        loadFiles();
      }, REFRESH_MS);
    }
  }

  function hasActiveUploads() {
    return activeUploads > 0 || pendingUploads.length > 0;
  }

  function apiGet(path) {
    return fetch(path, { credentials: "same-origin" }).then(function (response) {
      if (response.status === 401) {
        showLogin();
        throw new Error("unauthorized");
      }
      return response.json().catch(function () {
        return {};
      }).then(function (data) {
        if (!response.ok) {
          throw new Error(data.error || ("HTTP " + response.status));
        }
        return data;
      });
    });
  }

  function loadFiles() {
    byId("status-line").textContent = "";
    apiGet("/api/files").then(function (data) {
      readOnly = Boolean(data.read_only);
      byId("readonly-badge").hidden = !readOnly;
      byId("upload-input").disabled = readOnly;
      byId("drop-zone").classList.toggle("disabled", readOnly);
      renderFiles(data.files || []);
    }).catch(function (error) {
      if (error.message === "unauthorized") {
        return;
      }
      if (error.message === "shared_dir_unavailable") {
        byId("status-line").textContent = "共享目录不可用，请回到电脑上检查";
        return;
      }
      byId("status-line").textContent = "列表加载失败：" + error.message;
    });
  }

  function fileExtension(name) {
    var index = String(name || "").lastIndexOf(".");
    return index >= 0 ? name.slice(index + 1).toLowerCase() : "";
  }

  function isImage(file) {
    return IMAGE_RE.test(file.name || file.path || "");
  }

  function isVideo(file) {
    return VIDEO_RE.test(file.name || file.path || "");
  }

  function createPlaceholder(label, extraClass) {
    var tile = document.createElement("div");
    tile.className = "thumb thumb-placeholder" + (extraClass ? " " + extraClass : "");
    if (label) {
      tile.textContent = label;
    }
    return tile;
  }

  function createThumb(file) {
    if (!isImage(file)) {
      if (isVideo(file)) {
        var videoTile = createPlaceholder("", "thumb-video");
        videoTile.setAttribute("aria-label", "视频");
        videoTile.title = "视频";
        return videoTile;
      }
      var extension = fileExtension(file.name || file.path);
      return createPlaceholder(extension ? extension.slice(0, 4) : "文件");
    }

    var button = document.createElement("button");
    button.type = "button";
    button.className = "thumb-button";
    button.setAttribute("aria-label", "预览 " + file.path);

    var image = document.createElement("img");
    image.className = "thumb";
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    image.src = "/thumbnail?path=" + encodeURIComponent(file.path) +
      "&v=" + (file.mtime || 0) + "-" + (file.size || 0);
    image.addEventListener("error", function () {
      if (image.parentNode === button) {
        button.replaceChild(createPlaceholder("图片"), image);
      }
    });

    button.appendChild(image);
    button.addEventListener("click", function () {
      openPreview(file.path);
    });
    return button;
  }

  function renderFiles(files) {
    var list = byId("file-list");
    var empty = byId("empty-state");
    list.textContent = "";
    empty.hidden = files.length > 0;
    list.hidden = files.length === 0;

    imageFiles = files.filter(isImage);

    files.forEach(function (file) {
      var row = document.createElement("li");
      row.className = "file-row";

      var thumb = document.createElement("div");
      thumb.className = "file-thumb";
      thumb.appendChild(createThumb(file));

      var name = document.createElement("span");
      name.className = "file-name";
      name.textContent = file.path;

      var meta = document.createElement("span");
      meta.className = "file-meta";
      meta.textContent = formatSize(file.size) + " · " + formatDate(file.mtime);

      var link = document.createElement("a");
      link.className = "download";
      link.textContent = "下载";
      link.href = "/download?path=" + encodeURIComponent(file.path);
      link.setAttribute("download", file.name);

      row.appendChild(thumb);
      row.appendChild(name);
      row.appendChild(meta);
      row.appendChild(link);
      list.appendChild(row);
    });
  }

  function indexOfPreview(path) {
    for (var index = 0; index < imageFiles.length; index += 1) {
      if (imageFiles[index].path === path) {
        return index;
      }
    }
    return -1;
  }

  function showPreview(index) {
    var file = imageFiles[index];
    if (!file) {
      closePreview();
      return;
    }
    previewPath = file.path;
    byId("preview-name").textContent = file.path;
    byId("preview-image").alt = file.name || file.path;
    byId("preview-image").src = "/view?path=" + encodeURIComponent(file.path) +
      "&v=" + (file.mtime || 0) + "-" + (file.size || 0);
    byId("preview-status").textContent = imageFiles.length > 1
      ? (index + 1) + " / " + imageFiles.length
      : "";
    var multiple = imageFiles.length > 1;
    byId("preview-prev").disabled = !multiple;
    byId("preview-next").disabled = !multiple;
  }

  function openPreview(path) {
    var index = indexOfPreview(path);
    if (index < 0) {
      return;
    }
    previewReturnFocus = document.activeElement;
    byId("preview").hidden = false;
    showPreview(index);
    byId("preview-close").focus();
  }

  function stepPreview(delta) {
    if (!previewPath || !imageFiles.length) {
      return;
    }
    var index = indexOfPreview(previewPath);
    if (index < 0) {
      closePreview();
      return;
    }
    index = (index + delta + imageFiles.length) % imageFiles.length;
    showPreview(index);
  }

  function closePreview() {
    if (!previewPath) {
      return;
    }
    previewPath = null;
    byId("preview").hidden = true;
    byId("preview-image").removeAttribute("src");
    byId("preview-status").textContent = "";
    if (previewReturnFocus && previewReturnFocus.focus) {
      previewReturnFocus.focus();
    }
    previewReturnFocus = null;
  }

  function createUploadRow(file) {
    var row = document.createElement("li");
    row.className = "upload-row";

    var name = document.createElement("span");
    name.className = "upload-name";
    name.textContent = file.name;

    var progress = document.createElement("progress");
    progress.max = 100;
    progress.value = 0;

    var status = document.createElement("span");
    status.className = "upload-status";
    status.textContent = "等待中";

    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "secondary small";
    cancel.textContent = "取消";

    row.appendChild(name);
    row.appendChild(progress);
    row.appendChild(status);
    row.appendChild(cancel);
    byId("upload-queue").appendChild(row);

    return { row: row, progress: progress, status: status, cancel: cancel };
  }

  function enqueueFiles(fileList) {
    if (readOnly || !fileList || !fileList.length) {
      return;
    }
    Array.prototype.forEach.call(fileList, function (file) {
      pendingUploads.push({ file: file, ui: createUploadRow(file) });
    });
    pumpUploads();
  }

  function pumpUploads() {
    while (activeUploads < MAX_ACTIVE_UPLOADS && pendingUploads.length > 0) {
      uploadOne(pendingUploads.shift());
    }
  }

  function uploadOne(item) {
    var file = item.file;
    var ui = item.ui;
    var started = Date.now();
    var xhr = new XMLHttpRequest();

    activeUploads += 1;
    ui.status.textContent = "上传中";
    ui.cancel.hidden = false;

    xhr.open("PUT", "/api/upload?name=" + encodeURIComponent(file.name));
    xhr.setRequestHeader("X-Requested-With", "shareFile");

    xhr.upload.onprogress = function (event) {
      if (!event.lengthComputable || !event.total) {
        return;
      }
      var percent = Math.min(100, Math.round(event.loaded * 100 / event.total));
      var seconds = Math.max((Date.now() - started) / 1000, 0.001);
      var speed = event.loaded / seconds;
      ui.progress.value = percent;
      ui.status.textContent = percent + "% · " + formatSize(speed) + "/s";
    };

    xhr.onload = function () {
      activeUploads -= 1;
      ui.cancel.hidden = true;
      if (xhr.status === 201) {
        ui.progress.value = 100;
        ui.status.textContent = "完成";
        try {
          var data = JSON.parse(xhr.responseText);
          if (data.name && data.name !== file.name) {
            ui.status.textContent = "完成（保存为 " + data.name + "）";
          }
        } catch (error) {
          // 响应不是 JSON 时保留“完成”即可
        }
        loadFiles();
      } else if (xhr.status === 401) {
        ui.status.textContent = "登录已失效";
        showLogin();
      } else if (xhr.status === 403) {
        ui.status.textContent = "失败：只读或无权限";
      } else {
        ui.status.textContent = "失败：HTTP " + xhr.status;
      }
      pumpUploads();
    };

    xhr.onerror = function () {
      activeUploads -= 1;
      ui.cancel.hidden = true;
      ui.status.textContent = "网络错误";
      pumpUploads();
    };

    xhr.onabort = function () {
      activeUploads -= 1;
      ui.cancel.hidden = true;
      ui.status.textContent = "已取消";
      pumpUploads();
    };

    ui.cancel.onclick = function () {
      xhr.abort();
    };

    xhr.send(file);
  }

  function bindEvents() {
    byId("login-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var pin = byId("pin-input").value.trim();
      if (!/^\d{4}$/.test(pin)) {
        setLoginError("请输入 4 位数字口令");
        return;
      }
      setLoginError("");
      var button = byId("login-btn");
      button.disabled = true;

      fetch("/api/login", {
        method: "POST",
        credentials: "same-origin",
        headers: Object.assign({ "Content-Type": "application/json" }, CSRF_HEADERS),
        body: JSON.stringify({ pin: pin })
      }).then(function (response) {
        if (response.ok) {
          byId("pin-input").value = "";
          showFiles();
          return null;
        }
        return response.json().catch(function () {
          return {};
        }).then(function (data) {
          if (response.status === 429) {
            setLoginError("尝试次数过多，请等待 " + (data.retry || 60) + " 秒");
          } else {
            setLoginError("口令错误，请重试");
          }
        });
      }).catch(function () {
        setLoginError("网络错误，请检查连接");
      }).finally(function () {
        button.disabled = false;
      });
    });

    byId("refresh-btn").addEventListener("click", loadFiles);

    byId("upload-input").addEventListener("change", function (event) {
      enqueueFiles(event.target.files);
      event.target.value = "";
    });

    byId("logout-btn").addEventListener("click", function () {
      fetch("/api/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: CSRF_HEADERS
      }).catch(function () {
        return null;
      }).finally(showLogin);
    });

    var dropZone = byId("drop-zone");
    ["dragenter", "dragover"].forEach(function (name) {
      dropZone.addEventListener(name, function (event) {
        event.preventDefault();
        if (!readOnly) {
          dropZone.classList.add("hover");
        }
      });
    });
    ["dragleave", "drop"].forEach(function (name) {
      dropZone.addEventListener(name, function (event) {
        event.preventDefault();
        dropZone.classList.remove("hover");
      });
    });
    dropZone.addEventListener("drop", function (event) {
      if (!readOnly) {
        enqueueFiles(event.dataTransfer.files);
      }
    });

    document.addEventListener("dragover", function (event) {
      event.preventDefault();
    });
    document.addEventListener("drop", function (event) {
      event.preventDefault();
    });

    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && !byId("files-view").hidden && !hasActiveUploads()) {
        loadFiles();
      }
    });

    byId("preview-close").addEventListener("click", closePreview);
    byId("preview-prev").addEventListener("click", function () {
      stepPreview(-1);
    });
    byId("preview-next").addEventListener("click", function () {
      stepPreview(1);
    });
    byId("preview").addEventListener("click", function (event) {
      if (event.target === event.currentTarget) {
        closePreview();
      }
    });
    byId("preview-image").addEventListener("error", function () {
      if (previewPath) {
        byId("preview-status").textContent = "无法加载预览";
      }
    });

    document.addEventListener("keydown", function (event) {
      if (!previewPath) {
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closePreview();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        stepPreview(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        stepPreview(1);
      }
    });
  }

  function init() {
    bindEvents();
    fetch("/api/session", { credentials: "same-origin" })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.authed) {
          showFiles();
        } else {
          showLogin();
        }
      })
      .catch(showLogin);
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { isImage: isImage, isVideo: isVideo };
  }
})();
