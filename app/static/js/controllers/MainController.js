/* global angular */

'use strict';

var nash = angular.module('nash');

nash.controller('MainController', [
    '$scope',
    function($scope){
        $scope.sayHello = "Hello Nash!";
    }
]);
