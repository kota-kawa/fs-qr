(function (window) {
  'use strict';
  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var items = [], categories = [], listeners = [];
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function notify() { listeners.forEach(function (listener) { listener(items, categories); }); }
  function setAll(nextItems, nextCategories) { items = Array.isArray(nextItems) ? nextItems : []; categories = Array.isArray(nextCategories) ? nextCategories : []; notify(); }
  function getItems() { return items; }
  function getItem(id) { return items.find(function (item) { return Number(item.item_id) === Number(id); }); }
  function replace(item) { var index = items.findIndex(function (candidate) { return Number(candidate.item_id) === Number(item.item_id); }); if (index >= 0) { items.splice(index, 1, item); } else { items.push(item); } notify(); }
  function remove(id) { items = items.filter(function (item) { return Number(item.item_id) !== Number(id); }); notify(); }
  function snapshot() { return clone(items); }
  function restore(value) { items = value; notify(); }
  function subscribe(listener) { listeners.push(listener); return function () { listeners = listeners.filter(function (value) { return value !== listener; }); }; }
  function getCategories() { return categories; }
  modules.store = { setAll: setAll, getItems: getItems, getCategories: getCategories, getItem: getItem, replace: replace, remove: remove, snapshot: snapshot, restore: restore, subscribe: subscribe };
})(window);
