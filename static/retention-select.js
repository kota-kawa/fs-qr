(function () {
  function initRetentionSelect(wrapper) {
    const nativeSelect = wrapper.querySelector('select');
    if (!nativeSelect || wrapper.dataset.retentionEnhanced === 'true') {
      return;
    }

    const optionElements = [];
    const selectOptions = Array.from(nativeSelect.options);
    if (selectOptions.length === 0) {
      return;
    }

    wrapper.dataset.retentionEnhanced = 'true';
    wrapper.classList.add('is-enhanced');

    nativeSelect.setAttribute('aria-hidden', 'true');
    nativeSelect.tabIndex = -1;

    const arrow = wrapper.querySelector('.retention-select-arrow');
    if (arrow) {
      arrow.setAttribute('aria-hidden', 'true');
    }

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'retention-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');

    const menu = document.createElement('ul');
    const menuId = `${nativeSelect.id || 'retention'}-menu-${Math.random().toString(36).slice(2, 8)}`;
    menu.className = 'retention-select-menu';
    menu.id = menuId;
    menu.setAttribute('role', 'listbox');
    menu.tabIndex = -1;
    trigger.setAttribute('aria-controls', menuId);
    trigger.setAttribute('aria-expanded', 'false');

    const currentIndex = selectOptions.findIndex((option) => option.selected && !option.disabled);
    let activeIndex = currentIndex >= 0 ? currentIndex : 0;

    if (selectOptions[activeIndex] && selectOptions[activeIndex].disabled) {
      activeIndex = selectOptions.findIndex((option) => !option.disabled);
      if (activeIndex === -1) {
        activeIndex = 0;
      }
    }

    trigger.textContent = selectOptions[activeIndex] ? selectOptions[activeIndex].textContent : '';

    selectOptions.forEach((option, index) => {
      const item = document.createElement('li');
      item.className = 'retention-select-option';
      item.dataset.value = option.value;
      item.setAttribute('role', 'option');
      item.tabIndex = -1;
      const optionId = `${menuId}-option-${index}`;
      item.id = optionId;
      item.textContent = option.textContent;

      if (option.disabled) {
        item.setAttribute('aria-disabled', 'true');
      }

      if (option.selected) {
        item.classList.add('is-selected');
        item.setAttribute('aria-selected', 'true');
        activeIndex = index;
      }

      item.addEventListener('click', (event) => {
        event.preventDefault();
        if (option.disabled) {
          return;
        }
        selectOption(index, true);
        trigger.focus({ preventScroll: true });
      });

      item.addEventListener('mouseenter', () => {
        setActive(index, false);
      });

      optionElements.push(item);
      menu.appendChild(item);
    });

    const referenceNode = arrow && arrow.parentNode === wrapper ? arrow : null;
    wrapper.insertBefore(trigger, referenceNode);
    wrapper.appendChild(menu);

    let isOpen = false;

    function setActive(index, focusOption) {
      if (!optionElements[index] || selectOptions[index]?.disabled) {
        return;
      }

      optionElements.forEach((el) => el.classList.remove('is-active'));
      optionElements[index].classList.add('is-active');
      menu.setAttribute('aria-activedescendant', optionElements[index].id);
      activeIndex = index;

      if (focusOption) {
        optionElements[index].focus({ preventScroll: true });
        optionElements[index].scrollIntoView({ block: 'nearest' });
      }
    }

    function updateSelectedClasses(selectedIndex) {
      optionElements.forEach((el, idx) => {
        if (idx === selectedIndex) {
          el.classList.add('is-selected');
          el.setAttribute('aria-selected', 'true');
        } else {
          el.classList.remove('is-selected');
          el.removeAttribute('aria-selected');
        }
      });
    }

    function selectOption(index, closeAfterSelect) {
      const option = selectOptions[index];
      if (!option || option.disabled) {
        return;
      }

      nativeSelect.selectedIndex = index;
      trigger.textContent = option.textContent;
      updateSelectedClasses(index);
      setActive(index, false);
      activeIndex = index;

      const changeEvent = new Event('change', { bubbles: true });
      nativeSelect.dispatchEvent(changeEvent);

      if (closeAfterSelect) {
        closeMenu(true);
      }
    }

    function findNextEnabled(fromIndex, step) {
      if (optionElements.length === 0) {
        return fromIndex;
      }
      let index = fromIndex;
      for (let i = 0; i < optionElements.length; i += 1) {
        index = (index + step + optionElements.length) % optionElements.length;
        if (!selectOptions[index].disabled) {
          return index;
        }
      }
      return fromIndex;
    }

    function openMenu() {
      if (isOpen) {
        return;
      }
      isOpen = true;
      wrapper.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');
      setActive(activeIndex, true);
      document.addEventListener('pointerdown', handleOutsideClick, true);
      document.addEventListener('keydown', handleGlobalKeydown, true);
    }

    function closeMenu(focusTrigger) {
      if (!isOpen) {
        return;
      }
      isOpen = false;
      wrapper.classList.remove('is-open');
      trigger.setAttribute('aria-expanded', 'false');
      document.removeEventListener('pointerdown', handleOutsideClick, true);
      document.removeEventListener('keydown', handleGlobalKeydown, true);
      if (focusTrigger) {
        trigger.focus({ preventScroll: true });
      }
    }

    function handleOutsideClick(event) {
      if (!wrapper.contains(event.target)) {
        closeMenu(false);
      }
    }

    function handleGlobalKeydown(event) {
      if (!isOpen || event.key !== 'Tab') {
        return;
      }
      if (!wrapper.contains(event.target)) {
        closeMenu(false);
      }
    }

    function handleTriggerKeydown(event) {
      switch (event.key) {
        case 'ArrowDown':
        case 'Down':
          event.preventDefault();
          openMenu();
          setActive(findNextEnabled(activeIndex, 1), true);
          break;
        case 'ArrowUp':
        case 'Up':
          event.preventDefault();
          openMenu();
          setActive(findNextEnabled(activeIndex, -1), true);
          break;
        case 'Enter':
        case ' ': // Space
          event.preventDefault();
          if (isOpen) {
            closeMenu(false);
          } else {
            openMenu();
          }
          break;
        case 'Escape':
        case 'Esc':
          event.preventDefault();
          closeMenu(false);
          break;
        default:
          break;
      }
    }

    function handleMenuKeydown(event) {
      switch (event.key) {
        case 'ArrowDown':
        case 'Down':
          event.preventDefault();
          setActive(findNextEnabled(activeIndex, 1), true);
          break;
        case 'ArrowUp':
        case 'Up':
          event.preventDefault();
          setActive(findNextEnabled(activeIndex, -1), true);
          break;
        case 'Home':
          event.preventDefault();
          setActive(findNextEnabled(-1, 1), true);
          break;
        case 'End':
          event.preventDefault();
          setActive(findNextEnabled(0, -1), true);
          break;
        case 'Enter':
        case ' ': // Space
          event.preventDefault();
          selectOption(activeIndex, true);
          break;
        case 'Escape':
        case 'Esc':
          event.preventDefault();
          closeMenu(true);
          break;
        case 'Tab':
          closeMenu(false);
          break;
        default:
          break;
      }
    }

    trigger.addEventListener('click', () => {
      if (isOpen) {
        closeMenu(false);
      } else {
        openMenu();
      }
    });

    trigger.addEventListener('keydown', handleTriggerKeydown);
    menu.addEventListener('keydown', handleMenuKeydown);

    nativeSelect.addEventListener('change', () => {
      const newIndex = nativeSelect.selectedIndex;
      if (newIndex >= 0 && !selectOptions[newIndex].disabled) {
        trigger.textContent = selectOptions[newIndex].textContent;
        updateSelectedClasses(newIndex);
        setActive(newIndex, false);
        activeIndex = newIndex;
      }
    });

    setActive(activeIndex, false);
    updateSelectedClasses(nativeSelect.selectedIndex >= 0 ? nativeSelect.selectedIndex : activeIndex);

  }

  function initialise() {
    document
      .querySelectorAll('[data-retention-select]')
      .forEach((wrapper) => initRetentionSelect(wrapper));
  }

  window.addEventListener('DOMContentLoaded', initialise);
})();
