"use strict";

var assert = require("assert");
var app = require("./web/app.js");

function check(file, expectImage, expectVideo) {
  assert.strictEqual(
    app.isImage(file), expectImage, "isImage: " + (file.name || file.path)
  );
  assert.strictEqual(
    app.isVideo(file), expectVideo, "isVideo: " + (file.name || file.path)
  );
}

check({ name: "IMG_3720.png", path: "IMG_3720.png" }, true, false);
check({ name: "IMG_3719.jpeg", path: "photos/IMG_3719.jpeg" }, true, false);
check({ name: "photo.WEBP", path: "photo.WEBP" }, true, false);
check({ name: "clear.gif", path: "clear.gif" }, true, false);
check({ name: "clip.mp4", path: "clip.mp4" }, false, true);
check({ name: "record.MOV", path: "record.MOV" }, false, true);
check({ name: "notes.txt", path: "notes.txt" }, false, false);
check({ path: "no-name.png" }, true, false);

console.log("app.js file classification ok");
