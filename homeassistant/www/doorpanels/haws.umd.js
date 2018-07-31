(function(a,b){'object'==typeof exports&&'undefined'!=typeof module?b(exports):'function'==typeof define&&define.amd?define(['exports'],b):b(a.HAWS={})})(this,function(a){'use strict';function b(a){return{type:'auth',api_password:a}}function c(a){return{type:'auth',access_token:a}}function d(){return{type:'get_states'}}function e(){return{type:'get_config'}}function f(){return{type:'get_services'}}function g(){return{type:'get_panels'}}function h(a,b,c){var d={type:'call_service',domain:a,service:b};return c&&(d.service_data=c),d}function i(a){var b={type:'subscribe_events'};return a&&(b.event_type=a),b}function j(a){return{type:'unsubscribe_events',subscription:a}}function k(){return{type:'ping'}}function l(a,b){return{type:'result',success:!1,error:{code:a,message:b}}}function m(a,d){function e(f,g,h){var i=new WebSocket(a),j=!1,k=function(){if(i.removeEventListener('close',k),j)return void h(s);if(0===f)return void h(r);var a=-1===f?-1:f-1;setTimeout(function(){return e(a,g,h)},1e3)},l=function(a){var e=JSON.parse(a.data);switch(e.type){case u:d.authToken?i.send(JSON.stringify(b(d.authToken))):d.accessToken?i.send(JSON.stringify(c(d.accessToken))):(j=!0,i.close());break;case v:j=!0,i.close();break;case w:i.removeEventListener('message',l),i.removeEventListener('close',k),i.removeEventListener('error',k),g(i);break;default:}};i.addEventListener('message',l),i.addEventListener('close',k),i.addEventListener('error',k)}return new Promise(function(a,b){return e(d.setupRetry||0,a,b)})}function n(a){return a.result}function o(a){for(var b,c={},d=0;d<a.length;d++)b=a[d],c[b.entity_id]=b;return c}function p(a,b){var c=Object.assign({},a);return c[b.entity_id]=b,c}function q(a,b){var c=Object.assign({},a);return delete c[b],c}var r=1,s=2,t=3,u='auth_required',v='auth_invalid',w='auth_ok',x=function(a,b){this.url=a,this.options=b||{},this.commandId=1,this.commands={},this.eventListeners={},this.closeRequested=!1,this._handleMessage=this._handleMessage.bind(this),this._handleClose=this._handleClose.bind(this)};x.prototype.setSocket=function(a){var b=this,c=this.socket;if(this.socket=a,a.addEventListener('message',this._handleMessage),a.addEventListener('close',this._handleClose),c){var d=this.commands;this.commandId=1,this.commands={},Object.keys(d).forEach(function(a){var c=d[a];c.eventType&&b.subscribeEvents(c.eventCallback,c.eventType).then(function(a){c.unsubscribe=a})}),this.fireEvent('ready')}},x.prototype.addEventListener=function(a,b){var c=this.eventListeners[a];c||(c=this.eventListeners[a]=[]),c.push(b)},x.prototype.removeEventListener=function(a,b){var c=this.eventListeners[a];if(c){var d=c.indexOf(b);-1!==d&&c.splice(d,1)}},x.prototype.fireEvent=function(a,b){var c=this;(this.eventListeners[a]||[]).forEach(function(a){return a(c,b)})},x.prototype.close=function(){this.closeRequested=!0,this.socket.close()},x.prototype.getStates=function(){return this.sendMessagePromise(d()).then(n)},x.prototype.getServices=function(){return this.sendMessagePromise(f()).then(n)},x.prototype.getPanels=function(){return this.sendMessagePromise(g()).then(n)},x.prototype.getConfig=function(){return this.sendMessagePromise(e()).then(n)},x.prototype.callService=function(a,b,c){return this.sendMessagePromise(h(a,b,c))},x.prototype.subscribeEvents=function(a,b){var c=this;return this.sendMessagePromise(i(b)).then(function(d){var e={eventCallback:a,eventType:b,unsubscribe:function(){return c.sendMessagePromise(j(d.id)).then(function(){delete c.commands[d.id]})}};return c.commands[d.id]=e,function(){return e.unsubscribe()}})},x.prototype.ping=function(){return this.sendMessagePromise(k())},x.prototype.sendMessage=function(a){this.socket.send(JSON.stringify(a))},x.prototype.sendMessagePromise=function(a){var b=this;return new Promise(function(c,d){b.commandId+=1;var e=b.commandId;a.id=e,b.commands[e]={resolve:c,reject:d},b.sendMessage(a)})},x.prototype._handleMessage=function(a){var b=JSON.parse(a.data);switch(b.type){case'event':this.commands[b.id].eventCallback(b.event);break;case'result':b.success?this.commands[b.id].resolve(b):this.commands[b.id].reject(b.error),delete this.commands[b.id];break;case'pong':break;default:}},x.prototype._handleClose=function(){var a=this;if(Object.keys(this.commands).forEach(function(b){var c=a.commands[b],d=c.reject;d&&d(l(t,'Connection lost'))}),!this.closeRequested){this.fireEvent('disconnected');var b=Object.assign({},this.options,{setupRetry:0}),c=function(d){setTimeout(function(){m(a.url,b).then(function(b){return a.setSocket(b)},function(b){return b===s?a.fireEvent('reconnect-error',b):c(d+1)})},1e3*Math.min(d,5))};c(0)}},a.ERR_CANNOT_CONNECT=r,a.ERR_INVALID_AUTH=s,a.ERR_CONNECTION_LOST=t,a.createConnection=function(a,b){return void 0===b&&(b={}),m(a,b).then(function(c){var d=new x(a,b);return d.setSocket(c),d})},a.subscribeConfig=function(a,b){return a._subscribeConfig?a._subscribeConfig(b):new Promise(function(c,d){var e=null,f=null,g=[],h=null;b&&g.push(b);var i=function(a){e=Object.assign({},e,a);for(var b=0;b<g.length;b++)g[b](e)},j=function(a,b){var c;return i({services:Object.assign({},e.services,(c={},c[a]=b,c))})},k=function(a){if(null!==e){var b=Object.assign({},e.core,{components:e.core.components.concat(a.data.component)});i({core:b})}},l=function(a){var b;if(null!==e){var c=a.data,d=c.domain,f=c.service,g=Object.assign({},e.services[d]||{},(b={},b[f]={description:'',fields:{}},b));j(d,g)}},m=function(a){if(null!==e){var b=a.data,c=b.domain,d=b.service,f=e.services[c];if(f&&d in f){var g={};Object.keys(f).forEach(function(a){a!==d&&(g[a]=f[a])}),j(c,g)}}},n=function(){return Promise.all([a.getConfig(),a.getPanels(),a.getServices()]).then(function(a){var b=a[0],c=a[1],d=a[2];i({core:b,panels:c,services:d})})},o=function(a){a&&g.splice(g.indexOf(a),1),0===g.length&&f()};a._subscribeConfig=function(a){return a&&(g.push(a),null!==e&&a(e)),h.then(function(){return function(){return o(a)}})},h=Promise.all([a.subscribeEvents(k,'component_loaded'),a.subscribeEvents(l,'service_registered'),a.subscribeEvents(m,'service_removed'),n()]),h.then(function(d){var e=d[0],g=d[1],h=d[2];f=function(){a.removeEventListener('ready',n),e(),g(),h()},a.addEventListener('ready',n),c(function(){return o(b)})},function(){return d()})})},a.subscribeEntities=function(a,b){return a._subscribeEntities?a._subscribeEntities(b):new Promise(function(c,d){function e(a){if(null!==h){var b=a.data,c=b.entity_id,d=b.new_state;h=d?p(h,d):q(h,c);for(var e=0;e<j.length;e++)j[e](h)}}function f(){return a.getStates().then(function(a){h=o(a);for(var b=0;b<j.length;b++)j[b](h)})}function g(b){b&&j.splice(j.indexOf(b),1),0===j.length&&(i(),a.removeEventListener('ready',f),a._subscribeEntities=null)}var h=null,i=null,j=[],k=null;b&&j.push(b),a._subscribeEntities=function(a){return a&&(j.push(a),null!==h&&a(h)),k.then(function(){return function(){return g(a)}})},k=Promise.all([a.subscribeEvents(e,'state_changed'),f()]),k.then(function(d){var e=d[0];i=e,a.addEventListener('ready',f),c(function(){return g(b)})},function(){return d()})})},Object.defineProperty(a,'__esModule',{value:!0})});
