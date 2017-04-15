/* global angular */

'use strict';

var nash = angular.module('nash');

nash.controller('MainController', [
    '$scope',
    '$http',
    function($scope, $http){
        $scope.sayHello = "Hello Nash!";

        // Simple GET request example:
        $http({
            method: 'GET',
            url: '/_friends'
        }).then(function successCallback(response) {
            $scope.friends = response.data;
            console.log(response);
        }, function errorCallback(response) {
            console.log(respoonse);
        });

    }
]);
