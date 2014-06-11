/*
 * This file is part of Invenio.
 * Copyright (C) 2013, 2014 CERN.
 *
 * Invenio is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of the
 * License, or (at your option) any later version.
 *
 * Invenio is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Invenio; if not, write to the Free Software Foundation, Inc.,
 * 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

(function($){

    var DynamicFieldList = (function() {

      /**
       * Constructor.
       *
       * @param element html element on which the plugin
       * @param options dictionary
       * @constructor
       */
      function DynamicFieldList(element, options) {

        // ensure that there is jQuery selector available
        this.$element = $(element);
        this.options = $.extend({}, $.fn.dynamicFieldList.defaults, options);

        if (this.options.prefix === null) {
            this.options.prefix = this.attr('id');
        }
        this.template = this.$element.find('.' + options.empty_cssclass);
        this.last_index = $("#" + this.options.prefix + this.options.sep +  this.options.last_index);
        this.field_regex = new RegExp(
          "(" + this.options.prefix + this.options.sep + "(\\d+|" +
            this.options.index_suffix + "))"+ this.options.sep +"(.+)"
        );
        // Get template name from options or the empty elements data attribute
        this.tag_template = Hogan.compile($(this).data('tagTemplate') || '');

      }

      DynamicFieldList.prototype = {

        /**
         * Here initialization stuff. Especially the one which needs the plugin
         * to be already applied.
         */
        init: function() {

        },

        /**
         * Connecting events to functions, separated just to have them in one
         * place.
         */
        connectEvents: function() {

          // to have access to the class inside the events
          var that = this;

          this.$element.on('click', function(event) {
            that.doSomething(event.data.a);
          })
        },

        /**
         * Get next index
         */
        get_next_index: function(){
            return parseInt(last_index.val(), 10) + 1;
        },

        /**
         * Set value of last index
         */
        set_last_index: function(idx){
            return last_index.val(idx);
        },

        /**
         * Update attributes in a single tag
         */
        update_attr_index: function(tag, idx) {
            var id_regex = new RegExp("(" + this.options.prefix + this.options.sep + "(\\d+|" + this.options.index_suffix + "))");
            var new_id = this.options.prefix + this.options.sep + idx;
            ['for', 'id', 'name'].forEach(function(attr_name){
                if($(tag).attr(attr_name)){
                   $(tag).attr(attr_name, $(tag).attr(attr_name).replace(id_regex, new_id));
                }
            });
        },

        /**
         * Update index in attributes for a single element (i.e all tags inside
         * element)
         */
        update_element_index: function(element, idx) {
            this.update_attr_index(element, idx);
            $(element).find('*').each(function(){
                this.update_attr_index(this, idx);
            });
        },

        /**
         * Update indexes of all elements
         */
        update_elements_indexes: function(){
            // Update elements indexes of all other elements
            var all_elements = $('#' + this.options.prefix + " ." + this.options.element_css_class);
            var num_elements = all_elements.length;
            for (var i=0; i<num_elements; i++) {
                this.update_element_index(all_elements[i], i);
            }
            set_last_index(num_elements-1);
        },

        /**
         * Update values of fields for an element
         */
        update_element_values: function (root, data, field_prefix_index, selector_prefix){
            var field_prefix, newdata;

            if(selector_prefix ===undefined){
                selector_prefix = '#'+this.options.prefix+this.options.sep+this.options.index_suffix+this.options.sep;
            }

            if(field_prefix_index === undefined){
                field_prefix = this.options.prefix+this.options.sep+this.options.index_suffix+this.options.sep;
            } else {
                field_prefix = this.options.prefix+this.options.sep+field_prefix_index+this.options.sep;
            }
            if(root === null) {
                root = $(document);
            }

            //Update field values if data exists
            if(data !== null){
                // Remove prefix from field name
                newdata = {};
                if (typeof data == 'object'){
                    for(var field in data) {
                        if(field.indexOf(field_prefix) === 0){
                            newdata[field.slice(field_prefix.length)] = data[field];
                        } else {
                            newdata[field] = data[field];
                        }
                    }
                    // Update value for each field.
                    $.each(newdata, function(field, value){
                        var input = root.find(selector_prefix+field);
                        if(input.length !== 0) {
                            input.val(value);
                        }
                    });
                } else {
                    newdata['value'] = data;
                    var input = root.find('#'+this.options.prefix+this.options.sep+this.options.index_suffix);
                    if(input.length !== 0) {
                        // Keep old value
                        input.val(input.val()+data);
                    }
                }

                root.find("."+this.options.tag_title_cssclass).html(
                    tag_template.render(newdata)
                );
            }
        },

        get_field_name: function(name_or_id) {
            result = field_regex.exec(name_or_id);
            if(result !== null){
                return result[3];
            }
            return null;
        },

        get_field_prefix: function(name_or_id) {
            result = field_regex.exec(name_or_id);
            if(result !== null){
                return result[1];
            }
            return null;
        },

        /**
         * Handler for remove element events
         */
        remove_element: function(e){
            //
            // Delete action
            //
            e.preventDefault();

            // Find and remove element
            var old_element = $(this).parents("." + this.options.element_css_class);
            old_element.hide('fast', function(){
                // Give hide animation time to complete
                old_element.remove();
                update_elements_indexes();

                // Callback
                if (this.options.removed) {
                    this.options.removed(this.options, old_element);
                }
            });
        },

        /**
         * Handler for sort element events
         */
        sort_element: function (e, ui) {
            update_elements_indexes();
            // Callback
            if (this.options.updated) {
                this.options.updated(this.options, ui.item);
            }
        },

        update_element: function (data, idx){
            //
            // Update action
            //

            // Update elements indexes of all other elements
            var all_elements = $('#' + this.options.prefix + " ." + this.options.element_css_class);
            var num_elements = all_elements.length;
            if (idx < num_elements){
                element = $(all_elements[idx]);
                update_element_values(element, data, idx, '#'+this.options.prefix+this.options.sep+idx+this.options.sep);
            }
        },

        /**
         * Handler for add new element events
         */
        append_element: function (data, field_prefix_index){
            //
            // Append action
            //
            var new_element = template.clone();
            var next_index = get_next_index();
            // Remove class
            new_element.removeClass(this.options.empty_cssclass);
            new_element.addClass(this.options.element_css_class);
            // Pre-populate field values
            update_element_values(new_element, data, field_prefix_index);
            // Update ids
            this.update_element_index(new_element, next_index);
            // Insert before template element
            new_element.hide();
            new_element.insertBefore($(template));
            new_element.show('fast');
            // Update last_index
            set_last_index(next_index);
            // Add delete button handler
            new_element.find('.' + this.options.remove_cssclass).click(remove_element);
            // Add paste handler for some fields
            if( this.options.on_paste !== null && this.options.on_paste_elements !== null) {
                new_element.find(this.options.on_paste_elements).on('paste', on_paste);
            }
            // Callback
            if (this.options.added) {
                this.options.added(options, new_element);
            }
        },

        /**
         * On paste event handler, wrapping the user-defined paste handler to
         * for ease of use.
         */
        on_paste: function (e){
            var element = $(e.target);
            var root_element = element.parents("." + this.options.element_css_class);
            var data = e.originalEvent.clipboardData.getData("text/plain");
            var field_name = get_field_name(element.attr("id"));
            var prefix = "#" + get_field_prefix(element.attr("id")) + this.options.sep;

            if(this.options.on_paste !== null && data !== null) {
                if(this.options.on_paste(root_element, element, prefix, field_name, data, append_element)) {
                    e.preventDefault();
                }
            }
        },

        /**
         * Factory method for creating on paste event handlers. Allow handlers to
         * only care about splitting string into data elements.
         */
        create_paste_handler: function (splitter){
            var on_paste_handler = function(root_element, element, selector_prefix, field, clipboard_data, append_element){
                var elements_values = splitter(field, clipboard_data);
                if(elements_values.length > 0) {
                    $.each(elements_values, function(idx, clipboard_data){
                        if(idx === 0) {
                            update_element_values(root_element, clipboard_data, undefined, selector_prefix);
                        } else {
                            append_element(clipboard_data);
                        }
                    });
                    // Callback
                    if (this.options.pasted) {
                        this.options.pasted(this.options);
                    }
                    return true;
                } else {
                    return false;
                }
            };

            return on_paste_handler;
        },

        create: function(item){
            // Hook add/remove buttons on already rendered elements
            $('#' + this.options.prefix + " ." + this.options.element_css_class + " ." + this.options.remove_cssclass).click(remove_element);
            $('#' + this.options.prefix + " ." + this.options.add_cssclass).click(append_element);

            // Hook for detecting on paste events
            if( this.options.on_paste !== null && this.options.on_paste_elements !== null) {
                this.options.on_paste = create_paste_handler(this.options.on_paste);
                $('#' + this.options.prefix + " " + this.options.on_paste_elements).on('paste', on_paste);
            }

            // Make list sortable
            if(this.options.sortable){
                var sortable_options = {
                    items: "." + this.options.element_css_class,
                    update: sort_element,
                };

                if($(item).find("."+this.options.sort_cssclass).length !== 0){
                    sortable_options.handle = "." + this.options.sort_cssclass;
                }

                $(item).sortable(sortable_options);
            }

            return item;
        }

      }

      return DynamicFieldList;

    })();

    $.fn.dynamicFieldList = function(option) {
      return this.each(function() {
        var $this = $(this)
          , data = $this.data('dynamic-field-list')
          , options = typeof option == 'object' && option;
        // attach jQuery plugin
        if (!data) {
          data = new DynamicFieldList(this, options)
          $this.data('dynamic-field-list', data)
          data.init();
          data.connectEvents();
        }
      });
    };

    $.fn.dynamicFieldList.defaults = {
      prefix: null,
      sep: '-',
      last_index: "__last_index__",
      index_suffix: "__index__",
      empty_cssclass: empty_cssclass,
      element_css_class: "field-list-element",
      remove_cssclass: "remove-element",
      add_cssclass: "add-element",
      sort_cssclass: "sort-element",
      tag_title_cssclass: "tag-title",
      added: null,
      removed: null,
      updated: null,
      pasted: null,
      on_paste_elements: "input",
      on_paste: null, //paste_newline_splitter,
      sortable: true,
      js_template: null,
    };

    $.fn.dynamicFieldList.Constructor = DynamicFieldList;

})(jQuery);