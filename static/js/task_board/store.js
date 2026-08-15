(function (window) {
  'use strict';

  var modules = window.__FSQR_APP__.api.getModuleNamespace('taskBoard');
  var items = [];
  var categories = [];
  var listeners = [];

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function notify() {
    listeners.forEach(function (listener) {
      try {
        listener(items, categories);
      } catch (err) {
        console.error('Task store listener error:', err);
      }
    });
  }

  function extractCategoriesFromItems(itemList) {
    var set = new Set();
    itemList.forEach(function (it) {
      if (it.category && typeof it.category === 'string' && it.category.trim()) {
        set.add(it.category.trim());
      }
    });
    return Array.from(set).sort();
  }

  function setAll(nextItems, nextCategories) {
    items = Array.isArray(nextItems) ? nextItems : [];
    if (Array.isArray(nextCategories) && nextCategories.length > 0) {
      categories = nextCategories;
    } else {
      categories = extractCategoriesFromItems(items);
    }
    notify();
  }

  function getItems() {
    return items;
  }

  function getCategories() {
    return categories;
  }

  function getItem(id) {
    return items.find(function (item) {
      return Number(item.item_id) === Number(id);
    });
  }

  function replace(item) {
    var index = items.findIndex(function (candidate) {
      return Number(candidate.item_id) === Number(item.item_id);
    });
    if (index >= 0) {
      items.splice(index, 1, item);
    } else {
      items.push(item);
    }
    categories = extractCategoriesFromItems(items);
    notify();
  }

  function remove(id) {
    items = items.filter(function (item) {
      return Number(item.item_id) !== Number(id);
    });
    categories = extractCategoriesFromItems(items);
    notify();
  }

  function snapshot() {
    return clone(items);
  }

  function restore(value) {
    items = Array.isArray(value) ? value : [];
    categories = extractCategoriesFromItems(items);
    notify();
  }

  function subscribe(listener) {
    listeners.push(listener);
    return function () {
      listeners = listeners.filter(function (value) {
        return value !== listener;
      });
    };
  }

  modules.store = {
    setAll: setAll,
    getItems: getItems,
    getCategories: getCategories,
    getItem: getItem,
    replace: replace,
    remove: remove,
    snapshot: snapshot,
    restore: restore,
    subscribe: subscribe
  };
})(window);
