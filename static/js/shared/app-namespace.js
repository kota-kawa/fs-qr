(function (window) {
  var ROOT_KEY = '__FSQR_APP__';

  function isObjectLike(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  function createBucket() {
    return Object.create(null);
  }

  function createRoot() {
    var root = Object.create(null);

    Object.defineProperty(root, 'modules', {
      value: createBucket(),
      writable: false,
      configurable: false,
      enumerable: true
    });

    Object.defineProperty(root, 'config', {
      value: createBucket(),
      writable: false,
      configurable: false,
      enumerable: true
    });

    Object.defineProperty(root, 'shared', {
      value: createBucket(),
      writable: false,
      configurable: false,
      enumerable: true
    });

    return root;
  }

  function ensureNamespaceKey(name) {
    if (typeof name !== 'string' || name.length === 0) {
      throw new Error('Namespace key must be a non-empty string.');
    }
  }

  function ensureScopedBucket(bucket, scope) {
    ensureNamespaceKey(scope);
    if (!Object.prototype.hasOwnProperty.call(bucket, scope) || !isObjectLike(bucket[scope])) {
      bucket[scope] = Object.create(null);
    }
    return bucket[scope];
  }

  var root = window[ROOT_KEY];
  if (
    !isObjectLike(root)
    || !isObjectLike(root.modules)
    || !isObjectLike(root.config)
    || !isObjectLike(root.shared)
  ) {
    root = createRoot();
    Object.defineProperty(window, ROOT_KEY, {
      value: root,
      writable: false,
      configurable: false,
      enumerable: false
    });
  }

  if (!isObjectLike(root.api)) {
    var api = Object.freeze({
      getModuleNamespace: function (scope) {
        return ensureScopedBucket(root.modules, scope);
      },
      getConfig: function (scope) {
        ensureNamespaceKey(scope);
        if (!isObjectLike(root.config[scope])) {
          return {};
        }
        return root.config[scope];
      },
      setConfig: function (scope, value) {
        ensureNamespaceKey(scope);
        if (!isObjectLike(value)) {
          throw new Error('Config value must be an object.');
        }
        root.config[scope] = value;
      },
      getShared: function (key) {
        ensureNamespaceKey(key);
        return root.shared[key];
      },
      setShared: function (key, value) {
        ensureNamespaceKey(key);
        root.shared[key] = value;
      }
    });

    Object.defineProperty(root, 'api', {
      value: api,
      writable: false,
      configurable: false,
      enumerable: false
    });
  }
})(window);
