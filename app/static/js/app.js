/* global angular */

'use strict';

angular.module('nash', ['ngRoute'])
    .config(
        ['$routeProvider',
         '$locationProvider',
         function($routeProvider, $locationProvider) {
             $routeProvider
                 .when('/', {
                     templateUrl: 'static/partials/landing.html',
                     controller: 'MainController'
                 })
                 .when('/friends', {
                     templateUrl: 'static/partials/friends.html',
                     controller: 'MainController'
                 })
                 .otherwise({
                     redirectTo: '/'
                 });

             $locationProvider.html5Mode(true);
         }
        ]);
